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

## Acceptance Criteria
- **Given** `demand` with the fake backend returning yes once **when** an episode runs **then** exactly one plan call is recorded on that tick.
