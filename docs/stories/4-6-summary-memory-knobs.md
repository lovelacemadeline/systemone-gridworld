---
type: story
status: completed
title: Summary memory knobs — recent-action length and visit counts
owner: maddie
updated: 2026-10-16
anchor:
  - symbol: "src/gridworld/harness/memory.py::SummaryMemory"
  - symbol: "src/gridworld/harness/memory.py::make_memory"
  - test: "tests/test_memory.py::test_summary_k_and_visit_counts"
  - test: "tests/test_memory.py::test_visit_counts_on_a_back_and_forth_path"
  - test: "tests/test_memory.py::test_memory_knobs_reach_the_report"
---

# Story 4.6 — Summary memory knobs — recent-action length and visit counts

Follow-up to story 4.4. Watching E2B oscillate east/west at 0.95 confidence
with the k=3 recent-actions line present suggested a hypothesis: a short action
list gets pattern-completed, while a visit count might register. Two knobs on
`summary` memory test it:

- `--memory-k N` (default 3): length of the recent-actions list.
- `--memory-visits` (default off): appends visit counts to the summary tail,
  still inside the status line, e.g.
  `here (8,6) visited 12x; most visited: (8,6) 12, (9,6) 11, (7,5) 2`.

## Acceptance Criteria
- **Given** `--memory-k 10` **when** ten ticks have passed **then** the tail lists the last ten actions.
- **Given** `--memory-visits` **when** the player has moved back and forth **then** the tail gives the current cell's count and the three most-visited cells with counts.
- **Given** either knob **when** a run is reported **then** `meta.memory_k` and `meta.memory_visits` record it.

## Implementation notes

`SummaryMemory(k, visits)`. Counts include the start cell; ties among the most
visited cells break by cell order. Run names gain `-k<N>` / `-visits` when the
knobs are not at their defaults. Results of the two baseline runs with these
knobs are in story 5.4.
