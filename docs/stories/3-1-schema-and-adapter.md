---
type: story
status: pending
title: Vendored schema, request builder and validating adapter protocol
owner: maddie
updated: 2026-10-16
anchor: none  # outlined only
---

# Story 3.1 — Vendored schema, request builder and validating adapter protocol

Vendor `schema/systemone-{request,response}.schema.json` from the golden repo with the source commit in a README; `build_request(observation, mode, prefix)` producing a `choice` question over the six actions with the rendered state (text, or text plus base64 PNG block); a `Backend` protocol whose caller validates request and response against the schema.

## Acceptance Criteria
- **Given** a backend that returns an extra top-level field **when** called through the adapter **then** validation fails naming the field.
