---
type: story
status: completed
title: Step dynamics — movement, monsters, combat, termination
owner: maddie
updated: 2026-10-16
anchor:
  - symbol: "src/gridworld/sim.py::GridWorld.reset"
  - symbol: "src/gridworld/sim.py::GridWorld.step"
  - symbol: "src/gridworld/sim.py::GridWorld.observe"
  - symbol: "src/gridworld/sim.py::GridWorld.load"
  - symbol: "src/gridworld/sim.py::StepResult"
  - symbol: "src/gridworld/sim.py::attack_target"
  - test: "tests/test_sim.py::test_move_into_wall_is_noop_and_ticks"
  - test: "tests/test_sim.py::test_attack_removes_adjacent_monster_with_hp_1"
  - test: "tests/test_sim.py::test_monster_steps_toward_player_x_first_on_tie"
  - test: "tests/test_sim.py::test_monsters_never_enter_the_goal"
  - test: "tests/test_sim.py::test_hp_zero_ends_with_minus_one"
  - test: "tests/test_sim.py::test_goal_ends_with_plus_one_before_monsters_act"
  - test: "tests/test_sim.py::test_tick_limit_ends_with_zero"
  - test: "tests/test_sim.py::test_same_seed_and_actions_replay_identically"
---

# Story 1.2 — Step dynamics — movement, monsters, combat, termination

`step(action)`: moves blocked by walls and edges leave the player in place; `attack` damages a monster in an adjacent cell; monsters move one step toward the player when within a sight radius, else stay, with a deterministic tie-break; a monster adjacent to the player deals damage at end of tick; `wait` passes. Episode ends on goal reached, hp 0, or a tick limit. Reward is +1 goal, -1 death, 0 otherwise (only used for reports).

## As built

`GridWorld.step` returns `StepResult(observation, reward, done, info)`; `info`
carries `reason` (goal, dead, timeout or null), `moved`, `killed` and
`damage_taken`. One tick, in order (the `sim.py` module docstring is the
normative copy):

1. **Player.** A move into a wall, an edge or a monster is a no-op that still
   advances the tick. `attack` deals 1 to `attack_target` — the adjacent
   monster with least hp, then lowest id — and removes it at 0 hp; with nothing
   adjacent it is a no-op.
2. **Goal.** Stepping onto the goal ends the episode (+1) before monsters act.
3. **Monsters**, in id order: within Manhattan `sight_radius` and not already
   adjacent, step one cell toward the player along the axis with the larger
   gap (tie: x first), falling back to the other axis when blocked by a wall,
   another monster, the player or the goal. Monsters never enter the goal.
4. **Damage.** Each adjacent monster deals 1; hp 0 ends the episode (-1).
5. **Clock.** `tick` advances every step; reaching `tick_limit` (200) without
   another ending ends it with reward 0. Stepping a finished episode raises.

`GridWorld.load(observation)` continues from a hand-built state (used by the
tests). There is no hidden state: the next observation is a pure function of
the current one, the config and the action, so `(config, seed, actions)`
reproduces an episode exactly.

## Acceptance Criteria
- **Given** a wall to the north **when** `north` is stepped **then** the player position is unchanged and tick advances.
- **Given** an adjacent monster with hp 1 **when** `attack` is stepped **then** it is removed.
- **Given** the same seed and action list **when** replayed **then** the final observation is identical.
- **Given** a monster with equal x and y gaps to the player **when** it moves **then** it steps along x.
- **Given** the goal, hp 0 or the tick limit **when** reached **then** the episode ends with +1, -1 or 0.
