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

**Generation limits.** A plan call must not be kneecapped by chat defaults.
The golden server's chat route and mlx-lm's own server default to a few
hundred tokens, and the golden library's chat template forces thinking off for
decision prompts. The plan path sets its own `max_tokens` (default 4096,
`--plan-max-tokens`), passes the thinking toggle per call, and records
`finish_reason`; a plan that hit the cap is marked truncated in the tick record
and shown as such in the viewer, never passed off as a finished plan.

**Plan style.** `--plan direct|trace`: `direct` is a plain completion asking
for the plan in the fixed format; `trace` enables the model's thinking trace
first and keeps the trace in the record (not in the memory tail, which gets
only the final plan). Naming stays two-system: the decision model is System
One, both plan styles are System Two with different budgets.

## Acceptance Criteria
- **Given** a plan call that reaches `max_tokens` **when** recorded **then** the tick carries `plan_truncated: true` and the viewer marks it.
- **Given** `--plan trace` **when** a plan runs **then** the record holds the trace and the memory tail holds only the plan.
- **Given** a plan **when** the next tick renders **then** the plan appears in the volatile tail and the decision request is otherwise unchanged.
