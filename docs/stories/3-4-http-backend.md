---
type: story
status: pending
title: HTTP backend for /v1/systemone servers
owner: maddie
updated: 2026-10-16
anchor: none  # outlined only; depends on 3.1
---

# Story 3.4 — HTTP backend for /v1/systemone servers

httpx client with base URL, optional bearer token from an env var, timeout, and retries off by default so latency is honest.

## Acceptance Criteria
- **Given** a local mlx-classifiers server **when** one tick runs **then** the response validates and the request carried the prefix.
