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

## Implementation notes

First real run, 2026-10-16: `gridworld play --backend local --mode text --memory summary
--episodes 5 --seed 0` on `mlx-community/gemma-4-E2B-it-qat-4bit`, headless,
low power mode on, AC power, no fitted calibration. Headline table from
`runs/20261016T153243Z-local-mlx-community-gemma-4-e2b-it-qat-4bit-text-summary.md`:

| metric | value |
|---|---|
| episodes | 5 |
| ticks | 1000 |
| completion | 0.0% |
| died | 0.0% |
| timed out | 100.0% |
| cut short | 0.0% |
| oracle agreement | 0.0% |
| steps / oracle steps | - |
| distinct cells / steps | 0.01 |
| reversals / episode | 0.00 |
| decisions/s | 6.71 |
| p50 / p95 total ms | 146.96 / 160.81 |
| p50 / p95 backend ms | 146.88 / 160.72 |
| tokens / observation | 628.04 |
| mean cached tokens | 259.00 |
| mean top probability | 0.54 |

As in story 4.1's single episode, E2B answers `attack` on every tick and never
leaves its start cell (distinct cells / steps 0.01), so every episode times out.
The harness overhead is negligible (total ms is within 0.1 ms of backend ms).

