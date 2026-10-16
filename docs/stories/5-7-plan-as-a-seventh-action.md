---
type: story
status: completed
title: Plan as a seventh action
owner: maddie
updated: 2026-10-16
anchor:
  - symbol: "src/gridworld/backends/request.py::PLAN_OPTION"
  - symbol: "src/gridworld/backends/adapter.py::Decision"
  - symbol: "src/gridworld/harness/prompts.py::with_plan_option"
  - symbol: "src/gridworld/harness/think.py::SystemTwo.offer_plan"
  - symbol: "src/gridworld/harness/loop.py::Hooks"
  - symbol: "src/gridworld/harness/score.py::RunSummary"
  - symbol: "src/gridworld/view.py::render_frame"
  - test: "tests/test_action_think.py::test_plan_is_offered_after_wait_only_in_action_mode_and_not_while_cooling_down"
  - test: "tests/test_action_think.py::test_choosing_plan_makes_exactly_one_plan_and_reasks_without_the_option"
  - test: "tests/test_action_think.py::test_tick_cost_spends_the_planning_turn_as_wait"
  - test: "tests/test_action_think.py::test_plan_p_is_reported_like_pause_p"
  - test: "tests/test_action_think.py::test_the_prefix_gains_the_sentence_only_in_action_mode"
  - test: "tests/test_action_think.py::test_requests_in_other_modes_are_byte_identical_to_before"
  - test: "tests/test_action_think.py::test_viewer_shows_a_seventh_bar_when_plan_is_offered"
---

# Story 5.7 — Plan as a seventh action

`--think demand` (story 5.2) asks a second `noul` question on every tick, so
every decision costs two readouts. `--think action` offers planning as one of
the choices instead: the single `action` choice question gains a seventh
option, `plan`. One readout per tick covers both moving and thinking.

## Acceptance Criteria
- **Given** `--think action` **when** a tick is not cooling down **then** the
  action question's criteria end `wait`, `plan` (`plan`: "Pause to make a plan
  before acting (costs nothing in game time unless --think-cost tick)."), with
  or without the legal mask, and there is no second question.
- **Given** `--think action` **when** fewer than `--think-cooldown` ticks have
  passed since the last plan **then** `plan` is not offered.
- **Given** any other mode **when** a session runs **then** every request is
  byte-identical to before this story (sha256 pinned in the test).
- **Given** the fake backend choosing `plan` once with free cost **when** the
  episode runs **then** exactly one plan (reason `action`) is made on that
  tick and the action question is asked again on the same tick without
  `plan` and with the plan in the tail.
- **Given** `--think-cost tick` **when** `plan` is chosen **then** the tick's
  action is `wait` and there is no re-ask.
- **Given** a run **when** the report is written **then** P(plan) mean / p50
  / p90 and a ten-bin histogram are reported as P(pause) is for demand.

## Implementation notes

- `build_request(plan_option=True)` appends `PLAN_OPTION` to the criteria
  after the offered actions; `offered` stays the actions only. The loop asks
  the new `Hooks.offer_plan(obs, tick)` on a tick's first request only;
  `SystemTwo.offer_plan` returns true in action mode when cooled down.
- The adapter keeps `Decision.probabilities` over real actions; P(plan) is
  `Decision.plan_p`, and choosing it sets `Decision.chose_plan` with `action`
  set to the most likely real action. The six action probabilities are not
  renormalised, so on offered ticks they sum to `1 - P(plan)`.
- The decider's prefix gains `PLAN_OPTION_SENTENCE` (via
  `with_plan_option`, applied in `run_session`) only in action mode, so the
  report's `prefix_sha256` differs only there. The planner keeps the plain
  rules prefix.
- P(plan) is recorded per tick as `plan_p` (tick record and `TickLog`, absent
  on cooldown ticks); `EpisodeSummary.plan_p` and `RunSummary.plan_p_mean /
  _p50 / _p90 / _hist` carry it; the headline table has a `P(plan)` row and
  `gridworld compare` a `P(plan) mean` column.
- The viewer draws a seventh `plan` bar (always in its own blue) when the
  tick's probabilities include P(plan), live and on replay; plan panel and
  tick markers work as for the other triggers.
- The fake backend answers `plan` with `plan_p` (constant or `f(obs)`,
  default 0.05) and picks it when `plan_p >= 0.5`.
- No real-model run yet: the 26B was busy. Run it with
  `gridworld play --backend local --model mlx-community/gemma-4-26B-A4B-it-qat-4bit
  --think action --plan direct --labels words --legal-only --memory summary
  --episodes 5 --seed 0`.

## Follow-up (2026-10-16, after watching the 26B)

On a map where it ping-ponged, the 26B chose `plan` repeatedly and wrote the
same plan each time, because the plan prompt never showed it its previous
plan. The context now adds, from the second plan on, the plan count, the
previous plan text, and a nudge to choose a different route when moves are
repeating. First plans are unchanged. Anchor: `think.py::context_line`.
