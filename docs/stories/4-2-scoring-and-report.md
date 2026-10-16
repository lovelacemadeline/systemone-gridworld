---
type: story
status: completed
title: Scoring and the run report
owner: maddie
updated: 2026-10-16
anchor:
  - symbol: "src/gridworld/harness/score.py::summarize_run"
  - symbol: "src/gridworld/harness/score.py::RunSummary"
  - symbol: "src/gridworld/harness/score.py::oscillation"
  - symbol: "src/gridworld/harness/report.py::write_report"
  - symbol: "src/gridworld/harness/report.py::RunMeta"
  - test: "tests/test_report.py::test_noise_orders_agreement_and_completion"
  - test: "tests/test_report.py::test_run_summary_fields"
  - test: "tests/test_report.py::test_report_files_carry_provenance"
---

# Story 4.2 — Scoring and the run report

Per run over N episodes: oracle agreement, completion rate, mean steps over oracle steps, decisions/s, p50/p95 latency by phase, tokens per observation (from usage), mean top probability; markdown and JSON under `runs/` with backend id, mode, git rev, and power state.

## As built

- `harness/score.py` defines every metric in its module docstring.
  `EpisodeSummary` (story 4.1) carries agreement, outcome (won, died, timeout,
  or the harness cut-offs stopped and max_ticks), steps, oracle steps (the
  oracle plays the same seed separately), steps over oracle steps,
  oscillation (distinct cells / steps and immediate reversals), decisions/s,
  p50/p95 of total and backend ms, input, cached and per-observation tokens,
  and mean top probability. `summarize_run` aggregates: rates over episodes,
  agreement and means weighted by ticks, percentiles over all ticks.
- `harness/report.py::write_report` writes `runs/<stamp>-<backend>-<mode>-<memory>.md`
  and `.json` (the full `RunReport`). Provenance in `RunMeta`: backend id,
  model id (when the backend exposes `model_id`), mode, memory, git rev, power
  state (`pmset` low power mode and power source), world config, prefix
  length and sha256, start and finish times, and whether the run was
  interrupted. The markdown has a headline table and one row per episode.

## Acceptance Criteria
- **Given** two runs of the fake backend at noise 0 and 0.3 **when** reported **then** agreement and completion are ordered accordingly.
- **Given** a run **when** reported **then** the markdown and JSON carry backend id, mode, memory, git rev and power state.
