---
type: story
status: pending
title: Image mode through the local backend
owner: maddie
updated: 2026-10-16
anchor: none  # outlined only; depends on mlx-lm-as-classifiers Epic 6 (image blocks in the state)
---

# Story 3.5 — Image mode through the local backend

`LocalBackend` raises for image blocks today (story 3.3). Once the golden
library accepts `{"type": "image/png", "base64": ...}` blocks in a list
state (its Epic 6), re-vendor the schema, drop the image block from
`schema/local-extensions.md`, and let `--mode image` flow through
`decide` unchanged. Record encoder time per tick when the response's
`timing_ms` carries it. The text view stays in the request beside the image
by default (`--image-only` drops it) so text-plus-image and image-only can
be compared on identical states.

## Acceptance Criteria
- **Given** `--backend local --mode image` **when** one tick runs **then** the
  response validates against the re-vendored schema and the request carried
  one image block with the frame's sha256 recorded in the tick.
- **Given** the same seed **when** run in text, image, and text-plus-image
  modes **then** the report lists the three side by side.
