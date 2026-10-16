---
type: story
status: completed
title: Viewer plan panel and planning-tick markers
owner: maddie
updated: 2026-10-16
anchor:
  - symbol: "src/gridworld/view.py::render_frame"
  - symbol: "src/gridworld/view.py::LiveView.thinking"
  - symbol: "src/gridworld/view.py::LiveView.set_plan"
  - symbol: "src/gridworld/view.py::play_file"
  - test: "tests/test_view_plan.py::test_plan_panel_draws_only_with_system_two"
  - test: "tests/test_view_plan.py::test_truncated_badge_and_thinking_state"
  - test: "tests/test_view_plan.py::test_replay_plan_text_changes_on_recorded_ticks"
  - test: "tests/test_view_plan.py::test_live_view_shows_thinking_before_the_plan_call"
---

# Story 5.3 — Viewer plan panel and planning-tick markers

The side panel shows the current plan text (wrapped) and the tick strip marks planning ticks; the replay file carries the plan and its token cost per tick.

## Acceptance Criteria
- **Given** a replay with plans **when** viewed **then** the plan text changes on the recorded ticks.

## Implementation notes

- `render_frame` gains a plan panel under the session tallies when System Two
  is in play (`plan_ticks` not None): the current plan wrapped to the panel, a
  red `[truncated]` badge when the last plan hit its cap (truncated plans are
  never shown as the current plan), a yellow `thinking...` marker (and banner
  over the map) while a plan call runs, and a tick strip of recent ticks with
  planning ticks raised and highlighted and the current tick in white.
- `LiveView.thinking(obs)` draws that state before the blocking plan call
  (System Two calls it first); `LiveView.set_plan(tick, text, truncated)`
  records a plan; `run_session` resets the plan state per episode.
- Replays: tick lines carry the full `PlanResult` (plan, trace, style, tokens,
  finish reason, truncated, wall ms) plus `pause_p` (stories 5.1, 5.2), and
  `play_file` drives the panel from them, so the plan text changes on the
  recorded ticks.

