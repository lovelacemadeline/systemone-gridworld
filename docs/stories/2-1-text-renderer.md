---
type: story
status: pending
title: Text renderer with stable-first layout
owner: maddie
updated: 2026-10-16
anchor: none  # outlined only
---

# Story 2.1 — Text renderer with stable-first layout

`to_text(observation)` renders legend and map first and a single volatile status line last, so consecutive ticks share the longest possible token prefix. Fixed-width glyphs, row-major, with coordinates.

## Acceptance Criteria
- **Given** two consecutive observations that differ only in player position **when** rendered **then** the text differs only in the map cells moved and the status line.
