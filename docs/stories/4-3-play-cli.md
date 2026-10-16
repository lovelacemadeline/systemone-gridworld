---
type: story
status: completed
title: play CLI and headless CI run with the fake backend
owner: maddie
updated: 2026-10-16
anchor:
  - symbol: "src/gridworld/cli.py::main"
  - symbol: "src/gridworld/harness/session.py::run_session"
  - symbol: "src/gridworld/harness/session.py::session_lines"
  - symbol: "src/gridworld/view.py::LiveView.flash"
  - test: "tests/test_play.py::test_ci_five_fake_episodes"
  - test: "tests/test_play.py::test_world_flags_reach_header_and_report"
  - test: "tests/test_play.py::test_continuous_mode_stops_after_three_episodes"
  - test: "tests/test_play.py::test_keyboard_interrupt_still_writes_the_report"
  - test: "tests/test_play.py::test_view_without_pygame_names_the_extra"
  - test: "tests/test_play.py::test_continuous_view_headless_shows_tallies_and_flash"
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

## Implementation notes

- `gridworld play --backend fake|local|http --mode text|image --memory <mode>
  --episodes N (0 = until stopped) --seed S [--max-ticks T] [--prefix FILE]
  [--out runs] [--view --fps F --scale K --flash SECONDS]`, plus backend options
  `--noise --latency` (fake), `--model --int8` (local), `--url --timeout`
  (http). It prints the headline table and the report paths.
- **World flags**: `--width`, `--height`, `--monsters` (n_monsters), `--walls`
  (wall_density), `--hp` (player_hp), `--tick-limit`; defaults are
  `WorldConfig`'s. The config goes into every episode header and into the
  report's `meta.config`.
- `harness/session.py::run_session` plays seeds `seed, seed+1, ...`, records
  each to `runs/<name>/seed-NNNN.jsonl`, and rewrites the report after every
  episode and on exit. It stops when the view closes (Esc, q), when
  `on_episode` returns False (how the continuous-mode test stops after three),
  or on Ctrl-C, which marks the report `interrupted` and keeps the partial
  episode file (end reason `stopped`); that partial episode is not in the
  report's aggregates.
- The view gained `info_lines` (session tallies under the bars: episodes, win
  rate, steps over oracle steps, distinct cells over steps, reversals per
  episode, decisions/s) and `LiveView.flash(text, seconds)`, the result banner
  over the terminal frame.
- `--view` without pygame exits 2 with the message naming the `view` extra
  (checked before any backend loads).
- CI coverage: `test_ci_five_fake_episodes` runs 5 fake episodes headless for
  each mode and memory mode and checks the report, its oscillation fields and
  the episode files.
