---
type: story
status: pending
title: Live view window with probability bars and oracle overlay
owner: maddie
updated: 2026-10-16
anchor: none  # outlined only; depends on 2.2 and Epic 4
---

# Story 2.4 — Live view window with probability bars and oracle overlay

pygame window: map via the shared tiles, six probability bars with the chosen action highlighted and the oracle pick outlined, hp and tick, decisions/s. Works from a live loop or a replay file; optional dependency.

## Acceptance Criteria
- **Given** a replay file **when** `gridworld view <file>` runs **then** the episode plays at a chosen speed with no backend loaded.
