---
type: story
status: completed
title: Rule-based replan triggers — every N ticks, on damage, on reversals
owner: maddie
updated: 2026-10-16
anchor:
  - symbol: "src/gridworld/harness/think.py::SystemTwo.rule_reasons"
  - symbol: "src/gridworld/harness/think.py::SystemTwo.context_line"
  - symbol: "src/gridworld/harness/score.py::RunSummary"
  - test: "tests/test_rule_think.py::test_replan_every_10_over_30_ticks_gives_three_interval_plans"
  - test: "tests/test_rule_think.py::test_replan_on_damage_plans_on_the_tick_hp_dropped"
  - test: "tests/test_rule_think.py::test_replan_on_reversals_and_the_cooldown"
  - test: "tests/test_rule_think.py::test_coinciding_reasons_are_joined_and_the_prompt_says_why"
  - test: "tests/test_rule_think.py::test_reasons_are_summarised_in_the_report"
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

## Implementation notes

- `--think rule` with `--replan-every N`, `--replan-on-damage` and
  `--replan-on-reversals K`, in any combination (at least one is required).
  The check runs before the decision, so with free cost the decision already
  sees the fresh plan and no re-decide is needed. `interval` fires on ticks 0,
  N, 2N and so on; `damage` when hp is lower than on the previous tick;
  `reversals` after K immediate reversals since the last plan. Reasons that
  coincide join with `+` (e.g. `interval+damage`). `--think-cooldown` (default
  5) still applies; use 0 to replan on every hit.
- Every plan records its `reason` in `PlanResult` (`start`, `demand`, or the
  rule reasons). The episode and run summaries count `plan_reasons`, joint
  reasons counting toward each part, and the run markdown shows them.
- The plan prompt (all triggers) appends a context line to the rendered
  state: `Recent moves: west->(3,4), ... | hp 4 | Planning now because:
  scheduled refresh, you just lost hp`. A refreshed plan therefore sees the
  recent moves, current hp and why it is being asked.

## Run, 2026-10-16

`gridworld play --backend local --plan-model mlx-community/gemma-4-26B-A4B-it-qat-4bit
--think rule --replan-every 8 --replan-on-damage --plan direct --labels words
--legal-only --memory summary --episodes 5 --seed 0`, low power mode on, AC
power (`runs/story-5-6/20261016T163641Z-...-think-rule-direct`). E2B decides
and the 26B replans. The row is in the story 5.4 table beside the 26B-alone
and start-only split runs.

- **1 win, 2 deaths, 2 timeouts.** Seed 0 was won in 25 steps. Seeds 1 and 4
  ran 200 ticks with 25 plans each. The run made 61 plans (58 interval, 4
  damage, one tick both), none truncated, mean 82 completion tokens. The 26B
  took a median 5.9 s per plan (max 10.9 s), much faster than the expected 30
  s for these short direct plans.
- Against the start-only split (0 wins, 3 deaths, 78 reversals per episode),
  refreshing helps a little: reversals fall to 45 per episode and agreement is
  34%. But planning takes 82% of wall time (1.1 decisions/s), and the 26B
  deciding alone is still far better (4 of 5 won, 0 deaths) at 0.84
  decisions/s. Fresh plans from a strong model do not make up for a weak
  decider following them move by move.

