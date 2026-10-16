---
type: story
status: completed
title: Episode recording and replay
owner: maddie
updated: 2026-10-16
anchor:
  - symbol: "src/gridworld/record.py::EpisodeHeader"
  - symbol: "src/gridworld/record.py::TickRecord"
  - symbol: "src/gridworld/record.py::EpisodeEnd"
  - symbol: "src/gridworld/record.py::EpisodeRecorder"
  - symbol: "src/gridworld/record.py::read_episode"
  - symbol: "src/gridworld/record.py::replay"
  - symbol: "src/gridworld/record.py::ReplayMismatch"
  - test: "tests/test_record.py::test_recorded_episode_replays"
  - test: "tests/test_record.py::test_file_is_header_then_ticks_then_end"
  - test: "tests/test_record.py::test_read_episode_round_trips_fields_without_the_sim"
  - test: "tests/test_record.py::test_replay_detects_a_tampered_observation"
  - test: "tests/test_record.py::test_replay_detects_a_changed_action"
---

# Story 1.4 — Episode recording and replay

JSONL episode files: one header line (seed, map size, backend id, mode, git rev) then one line per tick with the observation, the action taken, the probabilities (if any), the oracle action, and timing. `replay(path)` yields observations for the live view without a backend.

## As built

`src/gridworld/record.py`. Every line is a JSON object discriminated by `kind`:

- `header` — `v`, `seed`, the full `WorldConfig` (map size plus density,
  monsters, hp, sight and tick limit, so the start state is rebuildable),
  `backend`, `mode`, `git_rev` (short HEAD via `git_rev()`, nullable).
- `tick` — the `observation` the decision was made on, the `action` taken,
  `probabilities` keyed by action name (nullable), `oracle_action`, and
  `timing` in milliseconds keyed by phase (nullable).
- `end` — the terminal `observation`, `reward` and `reason`. One extra line
  beyond the original spec: without it the state after the last action (the
  frame a viewer most wants to show) is not in the file. Optional, so a run
  cut short still reads.

`EpisodeRecorder(path, header)` is a context manager with `tick(...)` and
`end(...)`, flushing each line. `read_episode(path)` parses a file with no
simulator involved (the live view's path, story 2.4). `replay(path)` re-steps
a fresh `GridWorld` from the header with the recorded actions, yields each
observation once verified, and raises `ReplayMismatch` naming the tick of the
first disagreement (including a changed reward or end reason).

## Acceptance Criteria
- **Given** a recorded episode **when** replayed through the sim with its actions **then** every observation matches the recorded one.
- **Given** a file whose observation or action was edited **when** replayed **then** `ReplayMismatch` is raised naming the tick.
- **Given** a recorded episode **when** read with `read_episode` **then** header, probabilities, oracle action and timing round-trip without a simulator.
