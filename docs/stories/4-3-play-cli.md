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

**Continuous mode.** `--episodes 0` runs forever: on each episode end the view
flashes the result (won / died / timed out) for a moment, then the next seed
starts (seed increments from `--seed`). The side panel carries session tallies:
episodes played, win rate, mean steps over oracle steps, oscillation, and
decisions/s over the whole session. Esc or q stops cleanly; every episode is
recorded as it ends and the session report is written on exit, so stopping
early loses nothing.

## Acceptance Criteria
- **Given** `--episodes 0` with the fake backend headless and a stop signal after three episodes **when** run **then** three episode files and one session report exist.
- **Given** `--view` without pygame installed **when** run **then** a clear error names the extra to install.
