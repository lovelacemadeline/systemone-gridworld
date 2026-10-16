---
type: story
status: completed
title: Memory modes — none, summary, transcript
owner: maddie
updated: 2026-10-16
anchor:
  - symbol: "src/gridworld/harness/memory.py::NoMemory"
  - symbol: "src/gridworld/harness/memory.py::SummaryMemory"
  - symbol: "src/gridworld/harness/memory.py::TranscriptMemory"
  - symbol: "src/gridworld/harness/score.py::oscillation"
  - test: "tests/test_memory.py::test_summary_differs_from_none_only_in_the_status_line_and_names_three_actions"
  - test: "tests/test_memory.py::test_transcript_carries_prior_turns_and_cached_tokens_grow"
  - test: "tests/test_memory.py::test_oscillation_is_reported_per_memory_mode"
---

# Story 4.4 — Memory modes

Each tick is a fresh request by default (Markov). Add `--memory none|summary|transcript`:

- **none**: current observation only (baseline).
- **summary**: the last k actions and positions rendered into the volatile
  status line, bounded tokens, still one fresh request.
- **transcript**: a growing conversation; each tick appends the rendered
  state, the question, and the chosen label, and the next request is the whole
  thing plus the new tick. Cheap only when the backend's prefix cache hits on
  the longest common token prefix, so this mode is gated on that landing in the
  golden repo's server and reports `cached_tokens` per tick to prove it.

The report gains an **oscillation** metric: distinct cells visited divided by
steps, and the count of immediate reversals, so memory modes can be compared
on the thing they are meant to fix.

## Acceptance Criteria
- **Given** `summary` with k=3 **when** a tick renders **then** only the status
  line differs from `none`, and it names the last three actions.
- **Given** `transcript` **when** tick t runs **then** the request contains the
  t-1 prior turns and the recorded `cached_tokens` grows with t on a backend
  that supports prefix caching.
- **Given** a run **when** reported **then** oscillation is present per mode.

## Implementation notes

- `harness/memory.py`: a `Memory` gives the loop a `tail` (appended to the
  status line through `build_request(memory_tail=...)`), a `history` (prior
  turns for a list `state`), and is told each outcome via `observe`.
  `--memory` on `gridworld play` picks one; the run report and episode header
  record which.
- **summary** (`SummaryMemory`, k=3): `recent: east->(3,4), east->(4,4), north->(4,3)`,
  oldest first, `recent: none` on the first tick. Only the status line differs
  from `none`.
- **transcript** (`TranscriptMemory`): each prior turn is
  `<state text>\nWhich action next? <action>`; tick t's `state` is the t prior
  turns plus the current text (`build_request(history=...)`). The loop records
  `usage.cached_tokens` per tick. No real backend has delta prefix caching yet
  (golden repo story 3.4, outlined), so the growth test runs on
  `FakeBackend(prefix_cache=True)`, which simulates it (common-prefix
  characters // 4). On the golden server today, transcript requests are valid
  but re-prefill the growing state every tick, which is the gate the outline
  names.
- **Oscillation** is in every episode summary and run report
  (`distinct_cell_ratio`, `reversals`; defined in `harness/score.py`).
- The System Two plan seam (`Hooks.before_decision`, story 4.1) appends its
  text to the same memory tail.
