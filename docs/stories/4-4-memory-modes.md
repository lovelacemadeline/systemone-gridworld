---
type: story
status: pending
title: Memory modes — none, summary, transcript
owner: maddie
updated: 2026-10-16
anchor: none  # outlined only; depends on 4.1; transcript mode also depends on delta prefix caching in the golden repo's server
---

# Story 4.4 — Memory modes

Each tick is a fresh request by default (Markov). Add `--memory none|summary|transcript`:

- **none**: current observation only (baseline).
- **summary**: the last k actions and positions rendered into the volatile
  status line, bounded tokens, still one fresh request.
- **transcript**: a growing conversation; each tick appends the rendered
  state, the question, and the chosen label, and the next request is the whole
  thing plus the new tick. Cheap only when the backend's prefix cache hits on
  the longest common token prefix, so this mode is gated on that landing in the
  golden repo's server and reports `cached_tokens` per tick to prove it.

The report gains an **oscillation** metric: distinct cells visited divided by
steps, and the count of immediate reversals, so memory modes can be compared
on the thing they are meant to fix.

## Acceptance Criteria
- **Given** `summary` with k=3 **when** a tick renders **then** only the status
  line differs from `none`, and it names the last three actions.
- **Given** `transcript` **when** tick t runs **then** the request contains the
  t-1 prior turns and the recorded `cached_tokens` grows with t on a backend
  that supports prefix caching.
- **Given** a run **when** reported **then** oscillation is present per mode.
