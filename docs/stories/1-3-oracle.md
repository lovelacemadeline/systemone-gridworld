---
type: story
status: ready-for-dev
title: Scripted oracle policy
owner: maddie
updated: 2026-10-16
anchor: none  # not yet built; anchors added when src/gridworld/oracle.py lands
---

# Story 1.3 — Scripted oracle policy

`oracle(observation) -> action`: attack if a monster is adjacent and the player can win the exchange, otherwise the first step of the shortest path to the goal avoiding cells adjacent to monsters when possible, otherwise `wait`. Deterministic.

## Acceptance Criteria
- **Given** any generated map **when** the oracle plays an episode **then** it reaches the goal within the tick limit on at least 95% of 200 seeds, and the failures are listed by seed.
- **Given** an observation **when** the oracle is called twice **then** the action is the same.
