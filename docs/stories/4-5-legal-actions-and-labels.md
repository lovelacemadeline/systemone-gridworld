---
type: story
status: completed
title: Legal-action mask and label style
owner: maddie
updated: 2026-10-16
anchor:
  - symbol: "src/gridworld/sim.py::legal_actions"
  - symbol: "src/gridworld/backends/request.py::build_request"
  - symbol: "src/gridworld/backends/schema.py::extended_request_schema"
  - symbol: "src/gridworld/harness/score.py::RunSummary"
  - test: "tests/test_legal.py::test_legal_actions_match_step_on_200_seeds"
  - test: "tests/test_legal.py::test_legal_only_request_offers_the_legal_set_on_the_vendored_schema"
  - test: "tests/test_legal.py::test_label_style_words_validates_on_the_vendored_schema"
  - test: "tests/test_legal.py::test_legal_only_episode_records_offered_and_keeps_agreement"
  - test: "tests/test_legal.py::test_cli_flags_reach_the_report"
  - test: "tests/test_legal.py::test_vendored_schema_defines_label_style"
---

# Story 4.5 — Legal-action mask and label style

Two benchmark options found while probing why E2B answers `attack` forever
(story 4.1): with letter labels, option permutations flatten to uniform (label
bias); with the action words bound as first-token labels and only legal
actions offered, E2B walks toward the goal.

- `--legal-only` (default off, so the baseline stays honest): the `choice`
  criteria offer a move only if it does something (inside the map, not a wall,
  not a monster — those are no-ops in `step`), `attack` only with a monster
  edge-adjacent, `wait` always.
- `--labels letters|words`: `words` sends `options.label_style: "option-text"`
  (the golden repo's new option); `letters`, the default, omits the key.

## Acceptance Criteria
- **Given** 200 seeds of states **when** each action is stepped **then** it is in `legal_actions` iff it moves the player or damages/removes a monster, plus `wait`.
- **Given** `--legal-only` **when** a tick runs **then** the request offers exactly the legal set, the offered set is recorded per tick, and the report gives the mean number offered.
- **Given** `--labels words` **when** a request is built **then** it carries `options.label_style: "option-text"` and validates against the vendored schema.

## Implementation notes

- `sim.py::legal_actions(obs)` sits next to the movement rules and is checked
  against `step()` on every state of 200 noisy-oracle episodes.
- `build_request(..., legal_only, label_style)` returns the offered set;
  `adapter.call` now checks the choice and probabilities against the
  request's own criteria. Tick lines record `offered`; summaries report
  `mean_options_offered`; run names gain `-legal` / `-words` and the report
  meta records `legal_only` and `labels`.
- **Re-vendored.** While the vendored schema lacked `label_style` it was a
  second local extension, pinned by a strict-xfail target anchor. The golden
  repo landed it in 22f4d22; schema/ was re-vendored at 1e727aa
  (`schema/VENDORED.txt`), the extension removed (image blocks are again the
  only one), and `test_vendored_schema_defines_label_style` now passes.
- `LocalBackend` refuses `label_style` with a clear error when the installed
  mlx-classifiers lacks the field.

### E2B runs, 2026-10-16

`gridworld play --backend local --mode text --memory summary --episodes 5 --seed 0
[--labels words] [--legal-only] --out runs/story-4-5` (words re-runs: `runs/story-4-5-post`), headless,
`mlx-community/gemma-4-E2B-it-qat-4bit`, low power mode on, AC power, no fitted
calibration. The words runs used the golden library's uncommitted working
tree at first; the two words rows below are **post-landing numbers**, re-run
against the committed library (golden HEAD 1e727aa, clean) with the
re-vendored schema, low power mode on, AC power. Outcomes were identical to
the pre-landing runs; only decisions/s moved (6.39 to 6.79, 6.92 to 7.06). The letters / legal-only-off run overlapped a CPU-only test run, which
probably explains its lower decisions/s against story 4.2's 6.71.

| labels | legal-only | completion | died | agreement | distinct cells / steps | reversals / ep | decisions/s | mean options offered |
|---|---|---|---|---|---|---|---|---|
| letters | off | 0% | 0% | 0.0% | 0.01 | 0.0 | 5.54 | 6.00 |
| letters | on | 0% | 0% | 10.5% | 0.02 | 79.4 | 6.41 | 2.62 |
| words (post-landing) | off | 0% | 60% | 2.2% | 0.32 | 0.2 | 6.79 | 6.00 |
| words (post-landing) | on | 40% | 40% | 10.6% | 0.77 | 15.0 | 7.06 | 4.27 |

Per-episode outcomes: letters off, all five time out stuck on `attack`;
letters on, all time out, oscillating between two cells (79 reversals per
episode); words off, died on seeds 0, 2 and 3 and timed out on 1 and 4; words
on, won seeds 1 and 4 in 11 steps each (steps / oracle steps 0.92), died on 2
and 3, timed out on 0. Agreement stays low even when it wins: the model takes
different routes from the oracle.
