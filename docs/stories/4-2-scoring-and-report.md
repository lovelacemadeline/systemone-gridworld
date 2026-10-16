---
type: story
status: pending
title: Scoring and the run report
owner: maddie
updated: 2026-10-16
anchor: none  # outlined only; depends on 4.1
---

# Story 4.2 — Scoring and the run report

Per run over N episodes: oracle agreement, completion rate, mean steps over oracle steps, decisions/s, p50/p95 latency by phase, tokens per observation (from usage), mean top probability; markdown and JSON under `runs/` with backend id, mode, git rev, and power state.

## Acceptance Criteria
- **Given** two runs of the fake backend at noise 0 and 0.3 **when** reported **then** agreement and completion are ordered accordingly.
