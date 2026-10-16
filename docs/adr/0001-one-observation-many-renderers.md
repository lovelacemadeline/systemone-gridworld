---
type: decision
status: active
title: One structured observation; text, image and live view are lossless renderers of it
owner: maddie
updated: 2026-10-16
---

# ADR-0001 — One observation, many renderers

## Status
Active.

## Context
We want to compare a text endpoint with a vision endpoint on the same game,
and let a human watch either. If the text view and the image view are built
separately they will drift, and a mode comparison becomes a comparison of what
each mode was shown.

## Decision
The simulator emits **one structured observation** (grid cells, player,
monsters, items, hp, tick, last action). Every consumer is a pure function of
it: `to_text`, `to_image`, and the live window. Text and image are
**lossless**: a test decodes the image back to the grid and compares. The live
window draws with the same tile code the image renderer uses.

## Consequences
- A backend comparison across modes is a model comparison.
- Renderers are testable headless; the window is a thin pygame shell.
- Adding a mode (audio, a different text layout) is adding a renderer.

## Alternatives rejected
- **Text-only first, image later**: guarantees drift, and loses the live view
  that makes the benchmark watchable. Rejected.
