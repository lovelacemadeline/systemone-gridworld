---
type: story
status: ready-for-dev
title: Step dynamics — movement, monsters, combat, termination
owner: maddie
updated: 2026-10-16
anchor: none  # not yet built; anchors added when src/gridworld/sim.py lands
---

# Story 1.2 — Step dynamics — movement, monsters, combat, termination

`step(action)`: moves blocked by walls and edges leave the player in place; `attack` damages a monster in an adjacent cell; monsters move one step toward the player when within a sight radius, else stay, with a deterministic tie-break; a monster adjacent to the player deals damage at end of tick; `wait` passes. Episode ends on goal reached, hp 0, or a tick limit. Reward is +1 goal, -1 death, 0 otherwise (only used for reports).

## Acceptance Criteria
- **Given** a wall to the north **when** `north` is stepped **then** the player position is unchanged and tick advances.
- **Given** an adjacent monster with hp 1 **when** `attack` is stepped **then** it is removed.
- **Given** the same seed and action list **when** replayed **then** the final observation is identical.
