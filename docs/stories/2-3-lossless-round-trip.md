---
type: story
status: pending
title: Lossless round-trip test between text, image and observation
owner: maddie
updated: 2026-10-16
anchor: none  # outlined only; depends on 2.1 and 2.2
---

# Story 2.3 — Lossless round-trip test between text, image and observation

A decoder for each renderer that recovers the grid, player, goal, and monsters; tests assert both recover the observation. The decoder is test code, not product code.

## Acceptance Criteria
- **Given** 100 seeded observations **when** rendered to text and to image and decoded **then** all three agree.
