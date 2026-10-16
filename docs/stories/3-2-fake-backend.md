---
type: story
status: pending
title: Fake backend — oracle with controllable noise
owner: maddie
updated: 2026-10-16
anchor: none  # outlined only; depends on 3.1 and 1.3
---

# Story 3.2 — Fake backend — oracle with controllable noise

Returns the oracle action with probability p and a random other action otherwise, with plausible probability vectors, and a fixed per-call latency to make timing tests deterministic.

## Acceptance Criteria
- **Given** noise 0 **when** an episode runs **then** agreement is 100%.
