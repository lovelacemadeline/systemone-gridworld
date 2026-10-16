---
type: story
status: pending
title: Plan call over the chat route and plan injection into the memory tail
owner: maddie
updated: 2026-10-16
anchor: none  # outlined only; Epic 5 follows Epic 4
---

# Story 5.1 — Plan call over the chat route and plan injection into the memory tail

`plan(backend, obs, memory) -> str`: a chat completion on the same server (or in-process via the golden library) asking for a short plan in a fixed format (goal direction, route sketch, threats), capped in tokens. The plan text becomes part of the memory tail for the following ticks until replaced.

## Acceptance Criteria
- **Given** a plan **when** the next tick renders **then** the plan appears in the volatile tail and the decision request is otherwise unchanged.
