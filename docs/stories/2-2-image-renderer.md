---
type: story
status: pending
title: Image renderer and the shared tile code
owner: maddie
updated: 2026-10-16
anchor: none  # outlined only
---

# Story 2.2 — Image renderer and the shared tile code

`to_image(observation, tile=16)` draws the grid with one tile function per cell kind; the live view imports the same tile function.

## Acceptance Criteria
- **Given** an observation **when** rendered **then** the PNG is width*tile by height*tile plus a fixed status strip, and renders identically across runs.
