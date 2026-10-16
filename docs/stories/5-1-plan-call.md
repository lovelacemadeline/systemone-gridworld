---
type: story
status: completed
title: Plan call over the chat route and plan injection into the memory tail
owner: maddie
updated: 2026-10-16
anchor:
  - symbol: "src/gridworld/harness/plan.py::Planner"
  - symbol: "src/gridworld/harness/plan.py::LocalPlanner"
  - symbol: "src/gridworld/harness/plan.py::HTTPPlanner"
  - symbol: "src/gridworld/harness/plan.py::split_trace"
  - symbol: "src/gridworld/harness/think.py::SystemTwo"
  - symbol: "src/gridworld/harness/loop.py::Directive"
  - test: "tests/test_plan.py::test_start_plan_goes_into_the_tail_and_nothing_else_changes"
  - test: "tests/test_plan.py::test_trace_style_keeps_the_trace_out_of_the_tail"
  - test: "tests/test_plan.py::test_truncated_plan_is_recorded_as_such_and_not_injected"
  - test: "tests/test_plan.py::test_http_planner_request_shape"
  - test: "tests/test_plan.py::test_real_e2b_trace_plan"
---

# Story 5.1 — Plan call over the chat route and plan injection into the memory tail

`plan(backend, obs, memory) -> str`: a chat completion on the same server (or in-process via the golden library) asking for a short plan in a fixed format (goal direction, route sketch, threats), capped in tokens. The plan text becomes part of the memory tail for the following ticks until replaced.

**Generation limits.** A plan call must not be kneecapped by chat defaults.
The golden server's chat route and mlx-lm's own server default to a few
hundred tokens, and the golden library's chat template forces thinking off for
decision prompts. The plan path sets its own `max_tokens` (default 4096,
`--plan-max-tokens`), passes the thinking toggle per call, and records
`finish_reason`; a plan that hit the cap is marked truncated in the tick record
and shown as such in the viewer, never passed off as a finished plan.

**Plan style.** `--plan direct|trace`: `direct` is a plain completion asking
for the plan in the fixed format; `trace` enables the model's thinking trace
first and keeps the trace in the record (not in the memory tail, which gets
only the final plan). Naming stays two-system: the decision model is System
One, both plan styles are System Two with different budgets.

## Acceptance Criteria
- **Given** a plan call that reaches `max_tokens` **when** recorded **then** the tick carries `plan_truncated: true` and the viewer marks it.
- **Given** `--plan trace` **when** a plan runs **then** the record holds the trace and the memory tail holds only the plan.
- **Given** a plan **when** the next tick renders **then** the plan appears in the volatile tail and the decision request is otherwise unchanged.

## Implementation notes

- `harness/plan.py`: `Planner` protocol, `PlanResult` (plan, trace, style,
  completion/prompt tokens, finish_reason, truncated, wall_ms). The prompt is
  the rules prefix as system turn and the rendered state plus "Write a short
  plan: goal direction, route as a list of moves, threats to avoid. At most 80
  words." as user turn.
  - `LocalPlanner.from_backend(local_backend)` reuses the loaded mlx-lm model
    and tokenizer, renders with the tokenizer's own `apply_chat_template(...,
    enable_thinking=...)` (not the library's template, which forces thinking
    off), and calls `mlx_lm.generate.stream_generate` with a fresh KV cache, so
    the decision prefix cache is untouched.
  - `HTTPPlanner` POSTs `/v1/chat/completions` with `max_tokens`,
    `temperature` 0 and `enable_thinking`; it accepts the trace inline (think
    markers) or as `reasoning_content`. Tested on a mocked transport and on the
    golden Litestar app in-process (today's server ignores `enable_thinking`,
    so that test asserts the request reaches it with the right `max_tokens`); a
    live-server test is skipped unless `GRIDWORLD_SERVER_URL` is set.
  - `split_trace` understands Gemma 4's `<|channel>thought ... <channel|>` and
    `<think> ... </think>`. A call is truncated if it stopped on the cap or
    inside an unclosed trace; a truncated plan is recorded but never injected.
- `harness/think.py::SystemTwo` holds the episode's plan and appends
  `plan: <text>` (whitespace collapsed) to the status-line tail via
  `Hooks.before_decision` until replaced. The loop's hooks gained
  `extra_questions`, `after_decision` returning a `Directive` (re-decide, or
  override the action), and `tick_extras`; timing gained `think_ms`. Tick
  lines carry `plan` (the full `PlanResult`) and `pause_p`.
- CLI: `--think never|start` (story 5.2 adds `demand`), `--plan direct|trace`,
  `--plan-max-tokens` (default 4096). The planner follows the backend: local
  uses `LocalPlanner`, http `HTTPPlanner`, fake `FakePlanner`.

**Real trace plan**, 2026-10-16, E2B, seed 3 start state, `--plan trace`, cap
4096, low power mode on, AC power (`test_real_e2b_trace_plan`): not truncated
(finish `stop`), 887 completion tokens, 83 s wall, 2.4k characters of trace.
Plan: "Goal direction: North-West. Route: Move North repeatedly, then West.
Threats: M0 and M1 will advance towards you. Focus on reaching G (6, 2)
safely." The direction is right, but it swapped x and y on the goal (G is at
(2, 6)).

