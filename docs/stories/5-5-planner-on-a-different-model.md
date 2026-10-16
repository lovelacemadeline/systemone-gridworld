---
type: story
status: completed
title: Planner on a different model than the decider
owner: maddie
updated: 2026-10-16
anchor:
  - symbol: "src/gridworld/harness/plan.py::LocalPlanner.from_repo"
  - symbol: "src/gridworld/harness/plan.py::HTTPPlanner"
  - symbol: "src/gridworld/harness/report.py::RunMeta"
  - test: "tests/test_plan_model.py::test_from_repo_loads_a_separate_runner"
  - test: "tests/test_plan_model.py::test_planner_selection"
  - test: "tests/test_plan_model.py::test_flag_errors"
  - test: "tests/test_plan_model.py::test_separate_plan_server_ids_reach_header_and_report"
---

# Story 5.5 — Planner on a different model than the decider

The big-model experiment: decide with one model, plan with another, so
System Two can be a larger, slower model than System One.

- `--plan-model REPO` (local planner only): `LocalPlanner.from_repo` loads a
  second `MLXRunner` for that repo, with its own model, tokenizer and KV cache.
  Plans run on it while decisions stay on `--model`; both models stay resident.
- `--plan-backend local|http|fake` with `--plan-url URL`: the planner can be a
  separate `mlx-classifiers serve` process (the same `HTTPPlanner`, a
  different base URL).

## Acceptance Criteria
- **Given** `--plan-model REPO` **when** a plan runs **then** it uses a separately loaded runner for REPO, not the decider.
- **Given** `--plan-backend http --plan-url URL` **when** a plan runs **then** it is POSTed to URL's chat route.
- **Given** either **when** a run is reported **then** the report meta records the decider (`backend`, `model`) and the planner (`planner`, `planner_model`), and every episode header records `planner`.

## Implementation notes

- Planner selection (`cli.py::_planner`): `--plan-backend` defaults to the
  decision backend's kind. A local planner reuses the decider's weights unless
  `--plan-model` is given. `--plan-model` is accepted whenever the planner is
  local, which is slightly wider than "local backend only": a fake or HTTP
  decider with `--plan-backend local --plan-model` also works. `--plan-model`
  with a non-local planner, or `--plan-url` without `--plan-backend http`, exits
  2 with a message.
- `HTTPPlanner` now reads the trace from `message.reasoning`, the field the
  golden server's chat route returns since its story 3.5 (3d235c2), as well as
  `reasoning_content` and inline markers. It learns `planner_model` from the
  reply's `model`.
- **MoE note.** `mlx-community/gemma-4-26B-A4B-it-qat-4bit` is a
  mixture-of-experts model: mlx-lm 0.31.3's `gemma4_text` has `Router` and
  `Experts` modules behind `enable_moe_block`. The plan path only calls
  `apply_chat_template` and `stream_generate`, so it makes no dense
  assumption. The decision runner's own paths (`MLXRunner` prefill and
  readout) go through mlx-lm's model call. The golden `--int8` W8A8 patch
  (`patch_mlps`) targets dense MLPs and is unverified on the MoE layers, so do
  not combine `--int8` with the 26B.
- Tested with fakes only (`pytest -m "not mlx"`). No real two-model episode was
  run here: the 26B was running as the decider in this checkout at the time,
  and a second large load would have competed for memory.
