---
type: story
status: completed
title: Triggers — never, at start, on demand via a second noul question
owner: maddie
updated: 2026-10-16
anchor:
  - symbol: "src/gridworld/harness/think.py::SystemTwo.after_decision"
  - symbol: "src/gridworld/harness/think.py::SystemTwo.extra_questions"
  - symbol: "src/gridworld/harness/think.py::ThinkConfig"
  - test: "tests/test_think.py::test_demand_yes_once_gives_exactly_one_plan_on_that_tick"
  - test: "tests/test_think.py::test_demand_requests_carry_the_noul_and_free_cost_redecides"
  - test: "tests/test_think.py::test_threshold_and_cooldown"
  - test: "tests/test_think.py::test_tick_cost_with_a_monster_adjacent_spends_the_turn_as_wait"
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

## Implementation notes

- `--think never|start|demand`, `--think-threshold` (default 0.7),
  `--think-cooldown` (default 5 ticks between plans), `--think-cost free|tick`
  (default free). All are recorded in the run report's `meta.think`.
- **demand**: each tick's first request carries a second question,
  `pause_to_plan` (`noul`, "Should you pause to make a plan before acting?").
  Its P(yes) is logged on every tick line as `pause_p`. A plan fires when
  P(yes) >= threshold and the cooldown has elapsed.
- **free** cost: after the plan the decision is asked again with the plan in
  the tail and without the noul (`Directive(redecide=True)`), so a planning
  tick makes two decision calls. **tick** cost: the tick's action is `wait`
  (`Directive(action=wait)`) and the plan steers from the next tick; with
  `start`, that is tick 0.
- The fake backend answers `noul` questions with a constant or
  `f(observation, name)`, which is how the tests script "yes once". The adapter
  still parses only the `action` answer; System Two reads the noul from the raw
  response.

