---
type: story
status: completed
title: Stuck means no new cell — the rule fires on pacing and parking
owner: maddie
updated: 2026-10-17
anchor:
  - symbol: "src/gridworld/harness/loop.py::run_episode"
  - symbol: "src/gridworld/record.py::EpisodeEnd"
  - symbol: "src/gridworld/view.py::LiveView.streak_text"
  - test: "tests/test_stuck_skip.py::test_oscillating_backend_is_stuck_at_exactly_n"
  - test: "tests/test_stuck_skip.py::test_only_a_new_cell_resets_the_count"
  - test: "tests/test_stuck_skip.py::test_a_wait_does_not_reset_the_count"
  - test: "tests/test_stuck_skip.py::test_a_plan_does_not_reset_the_count"
  - test: "tests/test_stuck_skip.py::test_observed_pacing_and_parking_are_stuck"
  - test: "tests/test_stuck_skip.py::test_live_view_n_key_and_streak_text"
---

# Story 4.10 — Stuck means no new cell — the rule fires on pacing and parking

Story 4.9's `--stuck-after N` counted *consecutive immediate reversals* and
reset the count on any other tick and on every plan. It never fired in the
runs it was written for. In the E2B image run (vt140, summary memory, think
on with `replan_every 5`, `--stuck-after 10`, 2026-10-17) all ten episodes ran
the full 200 ticks to `timeout`:

- **seed 0** paced a column of 10 cells (distinct cells / steps 0.05, 114
  reversals) — but the reversals were interleaved with waits and attacks, each
  of which reset the count, and a plan every 5 ticks reset it regardless;
- **seed 7** walked to (0, 3) on tick 2 and answered `wait` for 197 ticks —
  0 reversals, so the count never moved.

With `replan_every` below N the plan reset alone made the rule unreachable.

**The contract now:** the loop counts the ticks since the player last entered a
cell it had not visited earlier in the episode (the start cell counts as
visited). A wait, a bump into a wall, an attack, a reversal and a step back
onto a known cell all add one; only a new cell resets the count, and a plan no
longer does. N reached ends the episode `stuck`, reward -1, as before. The end
line carries `stuck_after` and `ticks_without_new_cell` (the 4.9 field
`consecutive_reversals` is still accepted when reading older files). The
viewer's streak reads `no new cell K/N`. Everything else in 4.9 (precedence,
skip key, report columns) is unchanged. On the seed 0 / seed 7 traces the rule
now fires on tick 22 and tick 13 respectively with N = 10.

## Acceptance Criteria
- **Given** east/west oscillation on an open map and `stuck_after=4` **when** the episode runs **then**
  it is stuck after 5 ticks (one new cell, then four revisits) and the end line
  reads `stuck_after: 4, ticks_without_new_cell: 4`.
- **Given** west, east, west, west repeating **when** it runs **then** the count reads
  0, 1, 2, 0, 0, 1, 2, 0 — only a new cell resets it.
- **Given** east, west, east, wait with `stuck_after=3` **when** it runs **then** the wait adds
  one and the episode is stuck on tick 4.
- **Given** a planner replanning every 3 ticks and `stuck_after=5` **when** the oscillation runs **then** it is stuck after 6 ticks — plans do not reset the count.
- **Given** the recorded seed 0 and seed 7 action sequences replayed under the
  default world with a replan-every-5 planner and `stuck_after=10` **when** they run **then** the
  trajectories match the records and the episodes end `stuck` after 22 and 13
  ticks with `ticks_without_new_cell: 10`.
- **Given** the live view with a streak of 2 under `--stuck-after 4` **when** it draws **then**
  the `reversals/ep` line ends `no new cell 2/4`.

## Related
- [Story 4.9 — Stuck rule and a skip key](4-9-stuck-rule-and-skip-key.md)
