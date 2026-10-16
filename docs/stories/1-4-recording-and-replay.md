---
type: story
status: ready-for-dev
title: Episode recording and replay
owner: maddie
updated: 2026-10-16
anchor: none  # not yet built; anchors added when src/gridworld/record.py lands
---

# Story 1.4 — Episode recording and replay

JSONL episode files: one header line (seed, map size, backend id, mode, git rev) then one line per tick with the observation, the action taken, the probabilities (if any), the oracle action, and timing. `replay(path)` yields observations for the live view without a backend.

## Acceptance Criteria
- **Given** a recorded episode **when** replayed through the sim with its actions **then** every observation matches the recorded one.
