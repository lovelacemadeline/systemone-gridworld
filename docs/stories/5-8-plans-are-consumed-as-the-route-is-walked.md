---
type: story
status: completed
title: Plans are consumed as the route is walked
owner: maddie
updated: 2026-10-16
anchor:
  - symbol: "src/gridworld/harness/route.py::parse_route"
  - symbol: "src/gridworld/harness/route.py::RouteTracker"
  - symbol: "src/gridworld/harness/route.py::plan_for_tail"
  - symbol: "src/gridworld/harness/route.py::strip_action_line"
  - symbol: "src/gridworld/harness/think.py::ThinkConfig"
  - symbol: "src/gridworld/record.py::TickRecord"
  - symbol: "src/gridworld/view.py::LiveView.show_plan"
  - test: "tests/test_route.py::test_parse_route_is_tolerant"
  - test: "tests/test_route.py::test_route_tracker_consumes_deviates_and_exhausts"
  - test: "tests/test_route.py::test_the_tail_carries_the_remaining_route_and_exhaustion_drops_the_plan"
  - test: "tests/test_route.py::test_deviation_drops_the_plan"
  - test: "tests/test_route.py::test_exhaustion_ends_the_cooldown_and_plan_is_offered_again"
  - test: "tests/test_route.py::test_plan_persist_keeps_the_plan_and_the_original_route"
  - test: "tests/test_route.py::test_a_trailing_action_line_is_stripped_from_the_tail_but_kept_in_the_record"
  - test: "tests/test_route.py::test_regression_the_evidence_episode_drops_the_exhausted_plan_and_wins"
  - test: "tests/test_route.py::test_replay_shows_the_remaining_route_then_the_dropped_state"
  - test: "tests/test_route.py::test_live_view_is_told_the_remaining_route_and_the_drop"
---

# Story 5.8 — Plans are consumed as the route is walked

Until now a plan stayed in the memory tail, word for word, until the next plan
replaced it (story 5.1). The route in it goes stale one move at a time, and the
decider cannot tell which moves it has already made.

**Evidence** (2026-10-16, the 26B deciding and planning, `--think action
--plan direct --labels words --legal-only --memory summary`, seed 0):
`runs/20261016T181141Z-local-mlx-community-gemma-4-26b-a4b-it-qat-4bit-text-summary-legal-words-think-action-direct/seed-0000.jsonl`.
At tick 9, at (3,0) with the goal at (7,0), it chose `plan` and wrote
"Route: east, east, east, east, east, east, east." (seven easts), followed by
"Action: east" because the generation ran on into answering. A wall at (4,0)
forces the real path south and along row 1. The decider went south, east five
times past the goal's neighbour (7,1), north to (8,0), then east to (9,0)
(P(east) 0.99), then went back and forth between (8,0) and (9,0) for 190 ticks
until the tick limit, with P(plan) around 0.003. The plan text in the tail
outweighs the map, and a route that is off by one move is fatal.

## Acceptance Criteria
- **Given** a plan whose `Route:` line lists moves in any of these forms
  (commas, `then`, `x4` / `4 times` / `twice`, any case) **when** it is parsed
  **then** it becomes a list of moves; anything else on the line is ignored.
  A plan with no `Route:` line has no route and stays in the tail until
  replaced, as before.
- **Given** a plan with a route **when** each tick's action is taken **then**
  an action that matches the next move consumes it, and the tail carries the
  plan with the route line replaced by `remaining route: <moves>.`.
- **Given** the last move consumed (`exhausted`), or `--route-deviation-limit`
  (default 2) non-matching actions in a row (`deviated`) **when** the next
  tick is decided **then** the plan is not in the tail and that tick's record
  carries `plan_dropped: exhausted|deviated`. Under `--think action` the drop
  also ends the cooldown, so `plan` is offered on that tick.
- **Given** `--plan-persist` **when** a session runs **then** the plan stays
  in the tail with its original route until replaced (the old behaviour, for
  comparison).
- **Given** a plan ending in an `Action: ...` line **when** it is injected
  **then** that line is not in the tail (with or without `--plan-persist`);
  the tick record keeps the plan as generated.
- **Given** the viewer, live or on replay, **then** the plan panel shows the
  plan with the remaining route, and `plan dropped (<why>)` from the drop
  until the next plan.
- **Given** the evidence episode's decider actions for ticks 0 to 18 and a
  fake planner returning the tick-9 plan word for word **when** replayed
  **then** the route is consumed (south and north are misses that do not reach
  the limit of 2), exhausted by the seventh east at tick 18, dropped at tick 19
  with no later tick carrying the plan, and the fake (the oracle from tick 19)
  goes west twice onto G and wins at 21 steps. With `--plan-persist` the
  seven-east route is still in the tail at tick 19.

## Implementation notes

- `harness/route.py`: `parse_route`, `RouteTracker(moves, deviation_limit)`
  (`advance(action)` returns `active` / `exhausted` / `deviated`, `remaining`),
  `plan_for_tail(text, remaining)`, `strip_action_line`. The route span runs
  from `Route:` to the end of its line, or to the next `Label:` when the plan
  is on one line.
- `SystemTwo` keeps the stripped plan and its tracker. `observe_tick`
  advances the tracker with the tick's action; under `--think-cost tick` the
  planning tick's action (`wait`) does not count. `before_decision` drops an
  exhausted or deviated plan before building the tail, records
  `route_remaining` (the moves the decider saw) on every tick with a route,
  and passes the panel text to the view (`LiveView.show_plan`).
- New tick fields `route_remaining` and `plan_dropped` (on `TickRecord` and
  `TickLog`; older records read with both `None`). New config fields
  `ThinkConfig.plan_persist` and `route_deviation_limit`; CLI `--plan-persist`,
  `--route-deviation-limit`.
- Requests in other modes are unchanged: the 5.7 sha256 pins still hold,
  because the default fake plan has no `Route:` line.
- The brief expected the plan to drop "after the fourth east with the player
  on the goal". The map rules that out: the wall at (4,0) means four easts from
  (3,1) end at (7,1), beside the goal, and the plan's seven easts are not
  exhausted there. The regression test replays the actions actually recorded.
- No real-model run yet (the GPU was busy). Next step: rerun the evidence
  command on seeds 0 to 4, with and without `--plan-persist`.

## Follow-up (2026-10-16, after watching the 26B thrash)

On pocket maps (seed 7; the seed-0 map's wall bar) the planner wrote a route
straight into a wall, the tracker dropped it as deviated, the cooldown ended,
and the model replanned every three to six ticks with the same route. Two
changes: a deviated drop no longer ends the cooldown (an exhausted one still
does), and the plan context now carries the same legal-moves information the
decider gets ("From here you can move: east, south"), so the planner is not
blind to the wall beside it. Anchors: `think.py::SystemTwo._drop_if_done`,
`think.py::SystemTwo.context_line`.
