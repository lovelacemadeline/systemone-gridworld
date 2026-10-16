---
type: story
status: pending
title: play CLI and headless CI run with the fake backend
owner: maddie
updated: 2026-10-16
anchor: none  # outlined only; depends on 4.2
---

# Story 4.3 — play CLI and headless CI run with the fake backend

`gridworld play --backend fake|local|http --mode text|image --episodes N --seed S [--view] [--prefix FILE]`; CI runs 5 fake episodes headless in both modes and checks the report exists.

## Acceptance Criteria
- **Given** `--view` without pygame installed **when** run **then** a clear error names the extra to install.
