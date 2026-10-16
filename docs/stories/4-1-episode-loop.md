---
type: story
status: pending
title: Episode loop and decision log
owner: maddie
updated: 2026-10-16
anchor: none  # outlined only; depends on Epics 1 and 3
---

# Story 4.1 — Episode loop and decision log

`run_episode(sim, backend, mode, prefix, record)`: observe, render, build request, call backend, pick the choice, step, log one record per tick with probabilities, oracle action, and wall-clock timing split into render, backend, and step.

## Acceptance Criteria
- **Given** the fake backend **when** an episode runs headless **then** a JSONL record exists per tick and the episode terminates.
