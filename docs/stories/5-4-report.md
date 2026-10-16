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
| 26B decider alone (think never) | 80.0% | 0.0% | 56.1% | 0.77 | 0.84 | 3.97 | 0.00 | - | 0.0% | 30568 | - |
| E2B decides, 26B plans at start (5.5) | 0.0% | 60.0% | 49.0% | 0.52 | 4.39 | 3.13 | 1.00 | 78 | 30.6% | 59027 | - |
| E2B decides, 26B replans every 8 + on damage (5.6) | 20.0% | 40.0% | 33.9% | 0.46 | 1.10 | 3.41 | 12.20 | 82 | 82.5% | 69613 | - |
| 26B `--int8`, text (3.5 baseline) | 80.0% | 0.0% | 56.1% | 0.77 | 4.19 | 3.72 | 0.00 | - | 0.0% | 30392 | - |
| 26B `--int8`, text + image (3.5) | 100.0% | 0.0% | 64.3% | 0.79 | 0.76 | 3.96 | 0.00 | - | 0.0% | 28988 | - |
| 26B `--int8`, image only (3.5) | 40.0% | 20.0% | 52.8% | 0.47 | 0.73 | 4.06 | 0.00 | - | 0.0% | 63775 | - |
| 26B `--int8`, image transcript, no history (4.7) | 80.0% | 0.0% | 56.6% | 0.57 | 0.67 | 3.13 | 0.00 | - | 0.0% | 56038 | - |
| 26B `--int8`, image transcript, `--frames 3` (4.7) | 80.0% | 0.0% | 58.8% | 0.77 | 0.56 | 2.97 | 0.00 | - | 0.0% | 74870 | - |
| 26B `--int8`, image, sliding `--frame-window 3` (4.7) | 80.0% | 0.0% | 58.7% | 0.74 | 0.37 | 3.00 | 0.00 | - | 0.0% | 89284 | - |

The last three rows were added later, same flags and seeds. The 26B-alone and
start-only split rows are the coordinator's runs:
`runs/20261016T162447Z-local-mlx-community-gemma-4-26b-a4b-it-qat-4bit-text-summary-legal-words`
(won seeds 0 to 3 in 13 to 15 steps, timed out on 4, 33 reversals per episode)
and `runs/20261016T163023Z-local-mlx-community-gemma-4-e2b-it-qat-4bit-text-summary-legal-words-think-start-direct`
(`--plan-model` 26B; died on seeds 0, 2 and 3, timed out on 1 and 4, 78 reversals
per episode). The rule-replan row is story 5.6's run
(`runs/story-5-6/20261016T163641Z-...-think-rule-direct`).

The three story 3.5 rows (added later, same flags and seeds plus `--int8` and
the mode) are `--model` 26B in-process, golden 316f7c5, low power mode **off**,
AC power: `runs/story-3-5/20261016T195935Z-…-int8-text-summary-legal-words`,
`runs/story-3-5/20261016T200046Z-…-int8-image-summary-legal-words` and
`runs/story-3-5/20261016T200419Z-…-int8-image-only-summary-legal-words`.
Reversals per episode: 37.4 (text), 12.6 (text + image), 71.6 (image only).
Text + image is the first run to win seed 4 (in 99 steps). The text 26B ruts
there to the tick limit. Image decisions cost 1.29 s p50, against 0.24 s for
text with the int8 kernels and delta caching; about 0.7 s of that is the
vision encoder (story 3.5).

The three story 4.7 rows are `--mode image --memory transcript` with
`--frames 0`, `--frames 3` and `--frames 3 --frame-window`, under the same
conditions: `runs/story-4-7/20261016T202519Z-…-f0`, `…20261016T201733Z-…-f3`
and `…20261016T203315Z-…-fwin3`. Reversals per episode: 48.8 (no history),
36.8 (`--frames 3`), 36.8 (window). The window plays like the transcript but
at two thirds of its decisions/s.

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

