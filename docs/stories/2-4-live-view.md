---
type: story
status: completed
title: Live view window with probability bars and oracle overlay
owner: maddie
updated: 2026-10-16
anchor:
  - symbol: "src/gridworld/view.py::render_frame"
  - symbol: "src/gridworld/view.py::LiveView.update"
  - symbol: "src/gridworld/view.py::play_file"
  - symbol: "src/gridworld/view.py::DecisionRate"
  - symbol: "src/gridworld/view.py::ViewUnavailable"
  - symbol: "src/gridworld/cli.py::main"
  - symbol: "src/gridworld/record.py::record_episode"
  - test: "tests/test_view.py::test_map_is_the_image_renderer_scaled_up"
  - test: "tests/test_view.py::test_bars_follow_probabilities_and_colour_the_taken_action"
  - test: "tests/test_view.py::test_oracle_action_is_outlined"
  - test: "tests/test_view.py::test_play_file_headless"
  - test: "tests/test_view.py::test_live_view_blits_the_frame_and_tracks_decisions"
  - test: "tests/test_view.py::test_missing_pygame_names_the_extra"
  - test: "tests/test_view.py::test_cli_oracle_then_view"
---

# Story 2.4 — Live view window with probability bars and oracle overlay

pygame window: map via the shared tiles, six probability bars with the chosen action highlighted and the oracle pick outlined, hp and tick, decisions/s. Works from a live loop or a replay file; optional dependency.

## As built

- `view.py::render_frame` composes the whole window as a Pillow image: the
  `to_image` map scaled up with nearest-neighbour on the left (so the window
  shows exactly the PNG a vision backend sees, one drawing path, ADR-0001),
  and on the right hp and tick, decisions/s, and six bars in wire order. The
  taken action's bar uses its action colour, the others grey; the oracle's
  action is outlined in white. Pure and headless-testable.
- `LiveView` is the thin pygame shell: `update(obs, probabilities, action,
  oracle_action, timing)` blits the frame and returns `False` once the window
  is closed (Esc or q also close it) — the hook Epic 4's loop drives live.
  `DecisionRate` turns recorded `timing` (ms; `total`, else the sum of phases)
  into a running decisions/s, so a replay shows the original run's speed.
- `play_file(path, fps=4)` re-steps the file through `replay` first (proof it
  is reproducible), then plays it from `read_episode` with no backend.
- pygame is imported only when a window opens; without it `ViewUnavailable`
  names the `view` extra, and the CLI exits 2 with that message. The `view`
  extra now also lists Pillow, which the frame needs.
- `cli.py`: `gridworld view <episode.jsonl> [--fps N] [--tile T] [--scale S]
  [--no-verify] [--no-hold]`, plus `gridworld oracle --seed S --out FILE`,
  which records an oracle episode via `record.py::record_episode` so the viewer
  has something to play before Epic 4's `play` exists. Those files carry no
  probabilities or timing, so the bars show only the taken action.

Headless tests run pygame with `SDL_VIDEODRIVER=dummy`.

## Acceptance Criteria
- **Given** a replay file **when** `gridworld view <file>` runs **then** the episode plays at a chosen speed with no backend loaded.
- **Given** a frame **when** probabilities are present **then** bar lengths follow them, the taken action is coloured and the oracle action outlined.
- **Given** pygame is not installed **when** a window is opened **then** the error names the `view` extra.
