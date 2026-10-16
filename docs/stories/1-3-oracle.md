---
type: story
status: completed
title: Scripted oracle policy
owner: maddie
updated: 2026-10-16
anchor:
  - symbol: "src/gridworld/oracle.py::oracle"
  - symbol: "src/gridworld/oracle.py::play_episode"
  - test: "tests/test_oracle.py::test_oracle_completes_95_percent_of_200_seeds"
  - test: "tests/test_oracle.py::test_oracle_is_deterministic"
  - test: "tests/test_oracle.py::test_oracle_attacks_when_the_exchange_is_winnable"
  - test: "tests/test_oracle.py::test_oracle_routes_around_monster_adjacent_cells"
  - test: "tests/test_oracle.py::test_oracle_waits_when_goal_is_unreachable"
---

# Story 1.3 — Scripted oracle policy

`oracle(observation) -> action`: attack if a monster is adjacent and the player can win the exchange, otherwise the first step of the shortest path to the goal avoiding cells adjacent to monsters when possible, otherwise `wait`. Deterministic.

## As built

`oracle` in `src/gridworld/oracle.py` is a pure function of the observation:

1. **Fight** when a monster is adjacent and the player has more than 1 hp, or
   the monster `attack` would hit (`attack_target`, shared with the sim so the
   two agree on the target) has exactly 1 hp.
2. **Walk** the first step of `bfs_path` to the goal avoiding monster cells
   and every cell adjacent to a monster; if no such path exists, the first step
   of the plain path avoiding only walls and monster cells.
3. **Wait** when the goal is unreachable.

`play_episode(world, seed, policy=oracle)` runs a policy to the end and returns
its actions and last `StepResult` — reused by later harness stories as the
oracle-steps baseline.

**Balance.** Default `WorldConfig` (10x10, density 0.2, two monsters at hp 2,
sight 4) gives the oracle a 97.5% completion rate over seeds 0-199 with player
hp 6 and monsters spawned out of sight (story 1.1). At hp 5, or with monsters
spawning inside sight radius, it fell to about 93%, mostly to double-team
deaths. The completion test prints the failing seeds: 69, 142 and 169 die;
154 and 196 time out, oscillating as a monster that mirrors the player behind a
wall alternately opens and closes the safe path. The oracle is memoryless by
design, so that loop is accepted rather than patched.

## Acceptance Criteria
- **Given** any generated map **when** the oracle plays an episode **then** it reaches the goal within the tick limit on at least 95% of 200 seeds, and the failures are listed by seed.
- **Given** an observation **when** the oracle is called twice **then** the action is the same.
