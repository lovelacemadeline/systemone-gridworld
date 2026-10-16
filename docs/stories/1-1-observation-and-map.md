---
type: story
status: ready-for-dev
title: Observation record and map generation
owner: maddie
updated: 2026-10-16
anchor: none  # not yet built; anchors added when src/gridworld/sim.py lands
---

# Story 1.1 — Observation record and map generation

A pydantic `Observation` (width, height, walls as a set of cells, player, goal, monsters with hp, items, player hp, tick, last_action, seed) that is JSON-serialisable and hashable for replay. `generate_map(seed, width, height)` places walls so that a path from player to goal always exists (BFS check), with monsters off the shortest path at spawn.

## Acceptance Criteria
- **Given** a seed **when** `generate_map` runs twice **then** the observations are equal.
- **Given** any generated map **when** BFS runs from player to goal **then** a path exists.
- **Given** an observation **when** dumped to JSON and loaded **then** it is equal to the original.
