---
type: story
status: completed
title: Final frame and damage-first option
owner: maddie
updated: 2026-10-16
anchor:
  - symbol: "src/gridworld/sim.py::WorldConfig"
  - symbol: "src/gridworld/sim.py::GridWorld.step"
  - symbol: "src/gridworld/view.py::LiveView.hold_frame"
  - symbol: "src/gridworld/view.py::DecisionRate.recent_per_second"
  - symbol: "src/gridworld/view.py::play_file"
  - test: "tests/test_sim.py::test_goal_first_by_default_wins_onto_g_beside_a_monster_at_1_hp"
  - test: "tests/test_sim.py::test_damage_first_makes_the_same_step_a_death"
  - test: "tests/test_play.py::test_world_flags_reach_header_and_report"
  - test: "tests/test_final_frame.py::test_live_play_draws_the_end_observation_before_the_flash"
  - test: "tests/test_final_frame.py::test_replay_draws_the_end_observation_before_the_flash"
  - test: "tests/test_final_frame.py::test_rolling_rate_ignores_planning_and_old_ticks"
  - test: "tests/test_final_frame.py::test_rolling_rate_with_the_fake_backends_fixed_latency"
---

# Story 1.5 — Final frame and damage-first option

Three small fixes from watching the 26B in the viewer.

**The last move was never shown.** At the end of an episode the viewer drew
the frame from before the last move, then went straight to the result flash,
so the player seemed to jump onto G (or die without the hit being shown).

**The tick order was undocumented.** A tick runs player move, goal check,
monsters, damage, clock. So stepping onto G with 1 hp next to a monster is a
win. That stays the default and is now documented as a deliberate choice.
`--damage-first` provides the other order.

**The decisions/s figure looked too low.** The figure covers the whole
session, so plan calls and each map's first full prefill pull it down. Maddie
counted about 3/s by eye while the panel showed 1.2.

## Acceptance Criteria
- **Given** an episode ending in live play or in replay **when** it ends
  **then** the end observation is drawn with the last tick's bars and held for
  one normal frame interval, then the result is flashed (replay now flashes
  too: `gridworld view --flash`, default 1 s).
- **Given** the default rules **when** the player steps onto G with 1 hp beside
  a monster **then** the episode is won. The sim module docstring records
  goal-first as the chosen convention, because the prefix says "reach G to win"
  and damage happens at the end of the turn.
- **Given** `WorldConfig.damage_before_goal` (`--damage-first`) **when** the
  same step is taken **then** monsters next to the goal cell hit first and the
  episode is a death. With hp to spare it is still a win, with the hit taken.
  Ticks that do not reach the goal play out the same under both orders. The
  flag is in the episode header (`config`) and in the report's map line
  (`tick order: goal first|damage first`).
- **Given** the live panel **then** it shows `now X/s` next to the session
  `decisions/s`: a rolling rate over the last 10 decision ticks, with
  `think_ms` excluded. The session figure is unchanged.

## Implementation notes

- The loop's terminal `view.update` now passes the last tick's probabilities,
  action and oracle action, without timing so the rates are not counted twice.
  It then calls `hold_frame()` if the view has one. `LiveView.hold_frame` waits
  for nothing when `fps` is set, because the last update already waited one
  frame. Otherwise it waits for the recent mean decision tick, clamped to
  0.1 to 1 s. `play_file` does the same with the last tick record's bars, then
  flashes `seed N: WON|DIED|TIMED OUT`.
- `DecisionRate.recent` is a 10-tick deque of `total_ms - think_ms`.
  `recent_per_second` and `recent_tick_s` are derived from it, and
  `render_frame(recent_per_s=...)` draws the figure.
- Under damage-first, the hit on the goal step comes from monsters where they
  stand, because monsters do not move on a goal step in either order.
