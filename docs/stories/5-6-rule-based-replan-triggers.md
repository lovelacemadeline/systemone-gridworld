---
type: story
status: pending
title: Rule-based replan triggers — every N ticks, on damage, on reversals
owner: maddie
updated: 2026-10-16
anchor: none  # outlined only; follows 5.2 and 5.5
---

# Story 5.6 — Rule-based replan triggers

Findings behind this (2026-10-16, low power mode, seeds 0 to 4, words +
legal mask + summary memory): the 26B alone wins 4 of 5 with 56% oracle
agreement at 0.84 decisions/s; E2B alone wins 2 of 5 at 7 decisions/s; E2B
deciding with one 26B plan at episode start wins 0 of 5, dies 3 times, with
agreement up to 49% and reversals up to 78 per episode. E2B follows the plan
move by move, the plan is stale as soon as monsters move, and on-demand
triggering never fires because E2B's P(pause) sits at 0.05 regardless of
being stuck. The harness can see what the model cannot.

Add `--think rule` with `--replan-every N`, `--replan-on-damage`, and
`--replan-on-reversals K` (any combination; cooldown still applies). A
replan reuses the planner from 5.5, so the 26B can refresh E2B's plan while
E2B keeps deciding at full speed. The report records trigger reasons.

## Acceptance Criteria
- **Given** `--replan-on-damage` with the fake planner **when** hp drops
  **then** a plan is recorded on that tick with reason `damage`.
- **Given** `--replan-every 10` **when** 30 ticks run **then** three plans are
  recorded with reason `interval`.
- **Given** the E2B + 26B split on seeds 0 to 4 **when** run with
  `--replan-every 8 --replan-on-damage` **then** the 5.4 table gains the row.
