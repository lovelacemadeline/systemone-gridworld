---
type: story
status: completed
title: Report — quality versus cost across triggers
owner: maddie
updated: 2026-10-16
anchor:
  - symbol: "src/gridworld/harness/score.py::RunSummary"
  - symbol: "src/gridworld/harness/report.py::comparison_table"
  - symbol: "src/gridworld/cli.py::main"
  - test: "tests/test_report_think.py::test_plan_counts_tokens_time_and_pause_distribution"
  - test: "tests/test_report_think.py::test_never_has_no_plans_and_start_has_one_per_episode"
  - test: "tests/test_report_think.py::test_one_table_across_triggers"
---

# Story 5.4 — Report — quality versus cost across triggers

The run report gains plan count, plan tokens, and wall time in planning, so agreement and completion can be read against decisions/s and total tokens per episode for each trigger.

## Acceptance Criteria
- **Given** runs with the three triggers **when** reported **then** one table shows quality and cost side by side.

## Implementation notes

- Episode summaries gain plan count, truncated plans, plan completion and
  prompt tokens, `think_ms`, decision tokens and the per-tick P(pause). The run
  summary reports plans (per episode, truncated), plan tokens per plan,
  planning seconds and share of wall time (`total_ms` includes planning, so
  decisions/s pays for thinking), tokens per episode (decision plus plan), and
  P(pause) mean, p50, p90 and a ten-bin histogram. The run markdown's headline
  table shows them, and `meta.think` records the settings.
- `gridworld compare <report.json>...` prints one quality-versus-cost table, a
  row per run (`report.py::comparison_table`).

## Runs, 2026-10-16

`gridworld play --backend local --mode text --labels words --legal-only --memory summary
--episodes 5 --seed 0 --out runs/story-5-4` plus the flags in each row,
`mlx-community/gemma-4-E2B-it-qat-4bit`, headless, low power mode on, AC
power, golden library 1e727aa. The first row is a fresh 4.5 baseline (it
matches the story 4.5 post-landing numbers). The last two rows are the story
4.6 memory knobs.

| run | completion | died | agreement | distinct/steps | decisions/s | options | plans/ep | plan tok/plan | planning share | tokens/ep | P(pause) mean |
|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline (think never) | 40.0% | 40.0% | 10.6% | 0.77 | 7.00 | 4.27 | 0.00 | - | 0.0% | 29078 | - |
| think start, plan direct | 20.0% | 40.0% | 27.6% | 0.58 | 1.90 | 3.34 | 1.00 | 913 | 68.4% | 60969 | - |
| think demand, plan direct | 40.0% | 40.0% | 10.6% | 0.77 | 3.81 | 4.27 | 0.00 | - | 0.0% | 55412 | 0.05 |
| think demand, plan trace | 40.0% | 40.0% | 10.6% | 0.77 | 3.82 | 4.27 | 0.00 | - | 0.0% | 55412 | 0.05 |
| baseline, `--memory-k 10` | 20.0% | 40.0% | 27.4% | 0.56 | 6.88 | 3.47 | 0.00 | - | 0.0% | 54691 | - |
| baseline, `--memory-visits` | 40.0% | 40.0% | 10.6% | 0.77 | 6.73 | 4.24 | 0.00 | - | 0.0% | 31034 | - |

What the rows say:

- **demand never planned.** E2B's P(yes) for "Should you pause to make a plan
  before acting?" took only three values over 246 ticks (0.047, 0.053, 0.060;
  all in the lowest histogram bin), far below the 0.7 threshold, so both
  demand rows play exactly like the baseline. Their cost is the second
  question alone: decisions/s halves (7.0 to 3.8) and tokens per episode
  nearly double, because every tick prefills two prompts. A threshold near
  0.055 would make demand fire, but on a signal this flat that is close to
  random.
- **start/direct** made one plan per episode (5 plans, mean 913 completion
  tokens). Four were 96-154 tokens and took 3.5-5.4 s; the seed 3 plan fell into
  a repetition loop ("Move west to (9, 8), then south to (9, 9) is not
  possible...") and ran to the 4096 cap in 139 s. It was recorded as
  truncated and not injected. That one plan dominates the 68% planning share
  and the 1.9 decisions/s. Plans often get coordinates wrong (x and y swapped,
  as in story 5.1). Completion fell to 1/5, though agreement rose (27.6%)
  and the policy explores less (0.58 distinct cells per step).
- **k=10** looks like the start/direct row: agreement up, completion down, and
  more ticks spent (tokens per episode up). **visits** changed nothing
  measurable on these seeds. Neither confirms the hypothesis that a count
  would register where a short action list was pattern-completed.

