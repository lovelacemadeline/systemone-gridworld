---
type: story
status: pending
title: In-process backend over mlx-classifiers decide()
owner: maddie
updated: 2026-10-16
anchor: none  # outlined only; depends on 3.1
---

# Story 3.3 — In-process backend over mlx-classifiers decide()

Optional extra: wraps `mlx_classifiers.decide` with an `MLXRunner`, passing the prefix through so caching works. Skipped in CI without the library.

## Acceptance Criteria
- **Given** the golden library installed **when** one tick runs **then** the response validates and `output_tokens` is 0.
