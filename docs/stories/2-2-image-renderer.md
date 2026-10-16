---
type: story
status: completed
title: Image renderer and the shared tile code
owner: maddie
updated: 2026-10-16
anchor:
  - symbol: "src/gridworld/render/image.py::to_image"
  - symbol: "src/gridworld/render/image.py::to_png"
  - symbol: "src/gridworld/render/tiles.py::draw_tile"
  - symbol: "src/gridworld/render/tiles.py::draw_status"
  - test: "tests/test_image.py::test_size_is_map_plus_a_two_tile_status_strip"
  - test: "tests/test_image.py::test_renders_identically_across_runs"
  - test: "tests/test_image.py::test_cells_draw_in_their_tile_colours"
  - test: "tests/test_image.py::test_status_strip_shows_last_action_swatch"
---

# Story 2.2 — Image renderer and the shared tile code

`to_image(observation, tile=16)` draws the grid with one tile function per cell kind; the live view imports the same tile function.

## As built

- `render/tiles.py` is the only code that draws map pixels: `draw_tile` (one
  branch per kind: floor, wall, goal, player, monster) and `draw_status`, both
  over a Pillow `ImageDraw`. Flat-colour rectangles only — no anti-aliasing and
  no fonts (tick digits are a 3x5 bitmap font in `DIGITS`) — so pixels are
  identical across runs and platforms and decodable by sampling (story 2.3).
- `render/image.py::to_image(obs, tile=16)` returns an RGB `PIL.Image` of
  `width*tile` by `height*tile + 2*tile`: the map, then a status strip with
  player hp as pips, the tick in bitmap digits and the last action as a colour
  swatch. Monster hp shows as white pips on the monster tile; the player is an
  inner square whose border is the colour of what it stands on (goal when
  won). `to_png` encodes it.
- The live view (story 2.4) blits `to_image` output rather than drawing tiles
  itself, so window and PNG share one code path. Pillow is imported lazily via
  `gridworld.render.__getattr__`, keeping text-only use free of the extra.
- The test pins the raw-pixel sha256 of seed 3, so any change to what vision
  backends see is a deliberate one.

## Acceptance Criteria
- **Given** an observation **when** rendered **then** the PNG is width*tile by height*tile plus a fixed status strip, and renders identically across runs.
