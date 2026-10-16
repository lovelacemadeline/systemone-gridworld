---
type: story
status: completed
title: Stuck rule and a skip key
owner: maddie
updated: 2026-10-17
anchor:
  - symbol: "src/gridworld/harness/loop.py::run_episode"
  - symbol: "src/gridworld/record.py::EpisodeEnd"
  - symbol: "src/gridworld/harness/score.py::summarize_run"
  - symbol: "src/gridworld/harness/session.py::session_lines"
  - symbol: "src/gridworld/view.py::LiveView.streak_text"
  - test: "tests/test_stuck_skip.py::test_oscillating_backend_is_stuck_at_exactly_n"
  - test: "tests/test_stuck_skip.py::test_a_non_reversal_move_resets_the_count"
  - test: "tests/test_stuck_skip.py::test_a_plan_resets_the_count"
  - test: "tests/test_stuck_skip.py::test_skip_flag_ends_the_episode_with_reward_zero"
  - test: "tests/test_stuck_skip.py::test_skipped_episodes_are_listed_but_excluded"
  - test: "tests/test_stuck_skip.py::test_report_has_a_stuck_column_and_counts_stuck_as_not_completed"
  - test: "tests/test_stuck_skip.py::test_cli_stuck_after_reaches_the_report"
  - test: "tests/test_stuck_skip.py::test_live_view_n_key_and_streak_text"
---

# Story 4.9 — Stuck rule and a skip key

A model that ping-pongs between two cells burns the whole tick limit. The loop
now counts **consecutive immediate reversals** — a move that puts the player
back on the cell it occupied two ticks earlier, having moved away (the same
test as `oscillation`'s `reversals`). Any other tick resets the count, and so
does a tick on which System Two made a plan, so a replan gets a fresh chance.
`gridworld play --stuck-after N` (default 0 = off) ends the episode `stuck`
with reward -1 when the count reaches N; the end line carries `stuck_after`
and `consecutive_reversals`. `stuck` is a harness ending, so replay accepts it.

In the viewer, N sets `skip_requested`; the loop checks it after the tick and
ends the episode `skipped` with reward 0 (no final-frame hold). Skipped
episodes are recorded and listed, counted in the report's `skipped` row and
the panel's `skipped N`, but excluded from the completion / died / timed out /
stuck / cut short rates and from steps / oracle steps. The panel's
`reversals/ep` line gains `in a row K` (`K/N` with the rule on) so the streak
can be watched climbing.

## Acceptance Criteria
- **Given** a backend scripted to alternate east/west on an open map and
  `stuck_after=4` **when** the episode runs **then** it ends after 5 ticks
  (the move away, then four reversals) with reason `stuck`, reward -1, the end
  line's `stuck_after: 4, consecutive_reversals: 4`, summary `stuck: true`,
  and the file still replays; with the rule off it runs to the tick cap.
- **Given** a non-reversal tick (a `wait`) mid-oscillation **then** the count
  goes back to 0.
- **Given** a rule-triggered planner replanning every 3 ticks and
  `stuck_after=3` **when** the same oscillation runs **then** the count reads
  0, 1, 2 between plans and the episode is never stuck; without the planner it
  is stuck on tick 4.
- **Given** a view whose `skip_requested` is set by a hook **when** the tick
  ends **then** the episode ends `skipped` with reward 0 and the flag is
  cleared (a stale flag is also cleared at episode start).
- **Given** a three-episode session with one skipped **then** the summary has
  `skipped: 1`, completion 100%, the flash reads `seed 1: SKIPPED`, the panel
  reads `episodes 3   win 100%   skipped 1`, and the markdown lists the
  skipped episode and a `| skipped | 1 |` row.
- **Given** one won, one stuck and one skipped episode **then** completion
  and stuck are each 50%, the headline has a `stuck` row after `timed out`,
  and the comparison table has a `stuck` column after `died`.
- **Given** `--stuck-after 3` **then** `meta.stuck_after` is 3 and the
  markdown says `stuck after: 3`; a negative value exits 2.
- **Given** the live view **when** N is pressed **then** `skip_requested` is
  set; the `reversals/ep` line ends `in a row 2/4` for a streak of 2 under
  `--stuck-after 4`.
