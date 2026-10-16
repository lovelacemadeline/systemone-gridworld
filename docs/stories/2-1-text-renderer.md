---
type: story
status: completed
title: Text renderer with stable-first layout
owner: maddie
updated: 2026-10-16
anchor:
  - symbol: "src/gridworld/render/text.py::to_text"
  - symbol: "src/gridworld/render/text.py::status_line"
  - symbol: "src/gridworld/render/text.py::compass"
  - test: "tests/test_text.py::test_layout_is_legend_then_map_then_one_status_line"
  - test: "tests/test_text.py::test_glyphs_and_coordinates"
  - test: "tests/test_text.py::test_moving_changes_only_the_two_cells_and_the_status_line"
  - test: "tests/test_text.py::test_consecutive_ticks_share_prefix_up_to_the_first_moved_cell"
  - test: "tests/test_text.py::test_status_line_reports_threats_goal_and_last_action"
---

# Story 2.1 — Text renderer with stable-first layout

`to_text(observation)` renders legend and map first and a single volatile status line last, so consecutive ticks share the longest possible token prefix. Fixed-width glyphs, row-major, with coordinates.

## As built

`src/gridworld/render/text.py` (the module docstring is the normative layout):

1. A fixed three-line legend (glyphs, what each move does to x/y, combat).
2. `Map WxH, x across (0-W-1), y down (0-H-1):`, a column header of `x % 10`
   (fixed width on any map size), then one row per y with a right-aligned row
   number. Glyphs: `#` wall, `.` floor, `@` player, `G` goal, `M` monster.
3. One `Status:` line, always last: hp, tick, last action, adjacent monsters
   as compass directions, a compass hint toward the goal (`here` when the
   player stands on it), and every monster as `M<id> (x,y) hp N`.

Only the map cells the player and monsters occupy and the status line vary
between ticks, so a move changes two map characters plus the status line. The
monster list in the status line makes the text lossless for monster hp and id
(ADR-0001; checked by story 2.3). The seed and the reserved `items` field are
not rendered.

## Acceptance Criteria
- **Given** two consecutive observations that differ only in player position **when** rendered **then** the text differs only in the map cells moved and the status line.
- **Given** an observation **when** rendered **then** the legend comes first and the single status line last.
