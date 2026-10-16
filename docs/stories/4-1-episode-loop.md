---
type: story
status: completed
title: Episode loop and decision log
owner: maddie
updated: 2026-10-16
anchor:
  - symbol: "src/gridworld/harness/loop.py::run_episode"
  - symbol: "src/gridworld/harness/loop.py::Hooks"
  - symbol: "src/gridworld/harness/prompts.py::DEFAULT_PREFIX"
  - symbol: "src/gridworld/harness/score.py::summarize_episode"
  - symbol: "src/gridworld/harness/provenance.py::power_state"
  - test: "tests/test_loop.py::test_fake_episode_records_one_line_per_tick_and_terminates"
  - test: "tests/test_loop.py::test_max_ticks_cuts_the_episode_short_and_still_replays"
  - test: "tests/test_loop.py::test_hooks_inject_text_and_see_every_tick"
  - test: "tests/test_loop.py::test_view_closing_stops_the_episode"
  - test: "tests/test_loop.py::test_real_e2b_episode"
---

# Story 4.1 — Episode loop and decision log

`run_episode(sim, backend, mode, prefix, record)`: observe, render, build request, call backend, pick the choice, step, log one record per tick with probabilities, oracle action, and wall-clock timing split into render, backend, and step.

## As built

`harness/loop.py::run_episode(world, backend, *, seed, mode, prefix, memory,
record_path, view, hooks, max_ticks)` (the module docstring is the normative
tick order). Per tick: oracle action (untimed); render (memory tail, hook text,
history, `build_request`); `adapter.call`; step. The tick line records the
observation, action, probabilities, oracle action, usage and timing
`{render_ms, backend_ms, step_ms, total_ms}`; the memory is told the outcome;
`LiveView.update` runs when a view is given. Episodes end when the sim ends
them, at `max_ticks` (`max_ticks`), or when the view closes (`stopped`); a
KeyboardInterrupt still writes the end line, then propagates.

- **System Two seam (Epic 5)**: `Hooks.before_decision(obs, tick)` may return
  text appended to that tick's memory tail (a plan); `Hooks.after_tick(log)`
  sees each tick.
- `harness/prompts.py::DEFAULT_PREFIX` is the rules prefix; `load_prefix(path)`
  reads a `--prefix` file.
- Record format, additive within v1: tick lines gain optional `usage`, the
  header an optional `memory`; `replay` accepts harness cut-offs but rejects a
  cut-off that claims a sim ending.
- `run_episode` returns an `EpisodeSummary` from `harness/score.py::summarize_episode`
  (per-episode scoring lives here; story 4.2 adds the run aggregate and report).
- `harness/provenance.py::power_state` reads `pmset` (low power mode, power
  source); `None` off macOS.

## Implementation notes

Real episode, 2026-10-16, `LocalBackend` on `mlx-community/gemma-4-E2B-it-qat-4bit`,
text mode, memory none, seed 3, max 60 ticks (`test_real_e2b_episode`),
low power mode on, AC power: **max_ticks after 60 steps (oracle needs 18),
agreement 0.0, 6.7 decisions/s, p50 total 147 ms.** E2B answers `attack`
(about 0.55, with south about 0.27) on every tick from the start cell with no
monster adjacent, so it never moves. A real finding about the model and
prompt, not a harness fault: the compiled prompt was inspected and is correct.
Likely levers for later: option-order permutations (`options.permutations`),
calibration, or a larger model.

## Acceptance Criteria
- **Given** the fake backend **when** an episode runs headless **then** a JSONL record exists per tick and the episode terminates.
- **Given** `max_ticks` or a closed view **when** reached **then** the episode ends `max_ticks` or `stopped` and the file still replays.
