---
type: story
status: completed
title: Observation record and map generation
owner: maddie
updated: 2026-10-16
anchor:
  - symbol: "src/gridworld/sim.py::Observation"
  - symbol: "src/gridworld/sim.py::Monster"
  - symbol: "src/gridworld/sim.py::Action"
  - symbol: "src/gridworld/sim.py::WorldConfig"
  - symbol: "src/gridworld/sim.py::generate_map"
  - symbol: "src/gridworld/sim.py::bfs_path"
  - test: "tests/test_observation.py::test_generate_map_is_deterministic"
  - test: "tests/test_observation.py::test_generated_map_has_a_path_from_player_to_goal"
  - test: "tests/test_observation.py::test_generated_map_invariants"
  - test: "tests/test_observation.py::test_observation_json_round_trip"
  - test: "tests/test_observation.py::test_observation_is_hashable_and_frozen"
---

# Story 1.1 — Observation record and map generation

A pydantic `Observation` (width, height, walls as a set of cells, player, goal, monsters with hp, items, player hp, tick, last_action, seed) that is JSON-serialisable and hashable for replay. `generate_map(seed, config)` places walls so that a path from player to goal always exists (BFS check), with monsters off the shortest path at spawn.

## As built

- `Observation` is a frozen pydantic model in `src/gridworld/sim.py`. Cells are
  `(x, y)` with `(0, 0)` top-left. `walls` is a `frozenset` that serialises as
  a sorted list, so the JSON form is canonical; `monsters` is a tuple of frozen
  `Monster(id, pos, hp)` sorted by id; `items` is reserved and always empty in
  v1; `last_action` is `None` only at tick 0.
- `Action` is a `StrEnum` of exactly north, south, east, west, attack, wait, in
  that order — the option set every backend sees.
- `WorldConfig` carries map size (default 10x10), `wall_density` (0.2),
  `n_monsters` (2), `player_hp` (6), `monster_hp` (2), `sight_radius` (4) and
  `tick_limit` (200). With a seed it fully determines the start state.
- `generate_map` draws from one `random.Random(seed)`: walls at the configured
  density, player and goal on free cells at least `(width + height) // 2`
  apart, retried until `bfs_path` finds a route. Monsters spawn off that
  shortest path, never on the goal, and farther than `sight_radius` from the
  player (no monster is awake at tick 0) — a fairness rule added while tuning
  the oracle (story 1.3), because double-teams at spawn were the main cause of
  oracle deaths.
- Renderer invariant (ADR-0001): player, goal, walls and monsters occupy
  pairwise distinct cells, except the player on the goal in a won terminal
  state; monsters never enter the goal (story 1.2), so a text or image view
  never has to overlay a monster on the goal.

## Acceptance Criteria
- **Given** a seed **when** `generate_map` runs twice **then** the observations are equal.
- **Given** any generated map **when** BFS runs from player to goal **then** a path exists.
- **Given** an observation **when** dumped to JSON and loaded **then** it is equal to the original.
- **Given** an observation **when** hashed or mutated **then** equal observations hash equal and mutation raises.
