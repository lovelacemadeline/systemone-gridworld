---
type: story
status: pending
title: Triggers — never, at start, on demand via a second noul question
owner: maddie
updated: 2026-10-16
anchor: none  # outlined only; Epic 5 follows Epic 4
---

# Story 5.2 — Triggers — never, at start, on demand via a second noul question

`--think never|start|demand`. On demand adds a `noul` question "Should you pause to plan before acting?" to every tick; a yes above `--think-threshold` (default 0.7) triggers a plan before the action is taken, with a cooldown in ticks.

**Game-time cost of thinking.** The sim only advances on `step`, so by default
planning is free in game time: the plan runs before the action on the same
tick and monsters get no extra hit. `--think-cost free|tick` (default free):
with `tick`, choosing to plan consumes the turn as `wait`, so adjacent monsters
hit during deliberation and the action comes on the next tick. The report
shows both so the trade-off is measurable.

## Acceptance Criteria
- **Given** `--think-cost tick` and a plan triggered with a monster adjacent **when** the tick resolves **then** hp drops by one and the recorded action is `wait`.
- **Given** `demand` with the fake backend returning yes once **when** an episode runs **then** exactly one plan call is recorded on that tick.
