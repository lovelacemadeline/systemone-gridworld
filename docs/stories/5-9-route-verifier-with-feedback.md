---
type: story
status: pending
title: Route verifier with feedback — the planner is told when its route hits a wall
owner: maddie
updated: 2026-10-16
anchor: none  # outlined only; decision pending on whether this scaffolding belongs in the benchmark
---

# Story 5.9 — Route verifier with feedback

Evidence: `runs/20261016T183655Z-...-int8-...-think-action-direct/seed-0007.jsonl`.
The player starts in a two-cell pocket at (1,1)/(1,2) whose only exits are
north and west. Every one of the episode's 34 plans says "Route: south,
south, east, east" (the compass direction of the goal); south from (1,2) is
a wall. The decider cannot follow an unoffered move, goes north, then south,
the tracker drops the plan as deviated after two moves, P(plan) rises to 0.97,
and the next plan is identical. The 26B plans from the compass hint, not from
the map, and the previous-plan nudge (story 5.7 follow-up) cannot help when it
has no idea *why* the route failed.

Proposed: `--route-verify N` (default 0 = off). After a plan, the harness
walks the parsed route against the walls and edges from the current cell. If
a step is impossible, the planner is re-asked once per retry (up to N) with
feedback: "Your route hits a wall at step k from (x,y). Legal first moves
here: north, west." The final plan is used whether or not it verifies, and
the record carries `route_verified` and the retry count. This keeps the
planning in the model and only lends it a map check, but it is scaffolding,
and the report must label runs that use it.

The alternative is to leave seed 7 as a finding: "the 26B cannot plan around
walls from an ASCII map", which is the cleaner benchmark statement.

## Acceptance Criteria
- **Given** the seed-7 pocket and a fake planner that returns the recorded
  route first and a west-first route on feedback **when** `--route-verify 1`
  **then** the second plan is used and the player leaves the pocket.
- **Given** `--route-verify 0` **when** the same episode runs **then**
  behaviour and records are unchanged.
