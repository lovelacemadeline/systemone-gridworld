---
type: epic
status: completed
title: Simulator and oracle
epic: 1
owner: maddie
updated: 2026-10-16
---

# Epic 1 — Simulator and oracle

A deterministic gridworld: small rectangular map with walls, one player, a goal, a few monsters that move on simple rules, hp, and six actions (north, south, east, west, attack, wait). `reset(seed)`, `step(action) -> (observation, reward, done, info)`, `observe()`. The observation is one structured, serialisable record (ADR-0001). A scripted oracle gives the reference action for any observation. Episodes record to JSONL and replay.

## Stories
| id | title | status |
|---|---|---|
| 1.1 | Observation record and map generation | completed |
| 1.2 | Step dynamics — movement, monsters, combat, termination | completed |
| 1.3 | Scripted oracle policy | completed |
| 1.4 | Episode recording and replay | completed |
## Related
- [PRD](../product/prd-gridworld-benchmark.md), ADR-0001
