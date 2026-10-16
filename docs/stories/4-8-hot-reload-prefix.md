---
type: story
status: completed
title: Edit the rules prefix live — hot reload and an edit key
owner: maddie
updated: 2026-10-16
anchor:
  - symbol: "src/gridworld/harness/prompts.py::PrefixSource"
  - symbol: "src/gridworld/harness/prompts.py::edit_prefix"
  - symbol: "src/gridworld/harness/prompts.py::open_with_platform"
  - symbol: "src/gridworld/view.py::LiveView.prefix_lines"
  - test: "tests/test_prefix_reload.py::test_reload_follows_mtime_and_bumps_version_only_on_change"
  - test: "tests/test_prefix_reload.py::test_reload_lands_in_records_and_report"
  - test: "tests/test_prefix_reload.py::test_p_key_writes_default_once_switches_and_reaches_the_planner"
  - test: "tests/test_prefix_reload.py::test_platform_opener"
  - test: "tests/test_prefix_reload.py::test_cli_prefix_file_is_a_hot_source"
---

# Story 4.8 — Edit the rules prefix live

Prompt iteration without restarting a session. The rules prefix becomes a
`PrefixSource`: fixed text (the default) or a file re-read whenever its mtime
changes, with a version counter (from 1, bumped only when the text actually
changes) and a sha256. `run_episode` calls `current()` at the start of every
tick; the decider's prefix (with the plan-option sentence under
`--think action`) and the planner's prefix both come from that one read. The
harness invalidates nothing on a change — the backend's prefix cache sees a
new prefix and re-prefills it once.

`--prefix FILE` is now hot-reloaded. In the viewer, P opens the prefix for
editing with the platform opener (`open` on macOS, `xdg-open` elsewhere, via
`subprocess.Popen`): with `--prefix` it opens that file; without, it writes
the default text to `runs/<session>/prefix.txt` (only if absent) and the
session switches to that file. The panel shows `prefix v<N> (file|default)`
and, for a few seconds after a reload, `prefix reloaded at tick T`.

## Acceptance Criteria
- **Given** a file-backed source **when** the file is rewritten and its mtime
  moves **then** `current()` returns the new text and the version goes up; a
  touch with the same text, or an unreadable file mid-save, keeps the version.
- **Given** a reload during an episode **when** the next tick runs **then**
  that tick's record carries `prefix_reloaded: <version>`, the request sends
  the new text, the episode header carries `prefix_sha256` of the prefix at
  episode start, and the report's `meta.prefix_versions` lists every version
  used (the markdown names them when there is more than one).
- **Given** no `--prefix` **when** P is pressed (any number of times) **then**
  `prefix.txt` is written once with the default text, opened each time, the
  panel reads `prefix v1 (file)`, and after an edit the planner's next plan
  call uses the new text.
- **Given** `--prefix FILE` **when** P is pressed **then** that file is opened
  and nothing is written; a missing `--prefix` file exits 2.
