---
type: story
status: completed
title: Lossless round-trip test between text, image and observation
owner: maddie
updated: 2026-10-16
anchor:
  - symbol: "tests/decoders.py::decode_text"
  - symbol: "tests/decoders.py::decode_image"
  - test: "tests/test_roundtrip.py::test_text_image_and_observation_agree_on_100_seeds"
  - test: "tests/test_roundtrip.py::test_agree_on_every_state_of_noisy_episodes"
  - test: "tests/test_roundtrip.py::test_agree_on_other_map_sizes_and_tiles"
---

# Story 2.3 — Lossless round-trip test between text, image and observation

A decoder for each renderer that recovers the grid, player, goal, and monsters; tests assert both recover the observation. The decoder is test code, not product code.

## As built

`tests/decoders.py` holds `decode_text` (parses the map rows and the status
line) and `decode_image` (samples tile centres for the cell kind, the player
tile's border for what it stands on, white pips for monster hp, and the status
strip for hp pips, bitmap tick digits and the last-action swatch). Both return
a `Decoded` record of width, height, walls, player, goal, monsters as
`(cell, hp)`, player hp, tick and last action; `from_observation` builds the
same record from the truth.

What "lossless" covers, stated exactly: everything a policy can act on. Not
rendered by either view: the seed and the reserved `items` field. Monster ids
are in the text (and checked) but not in the image, which is fine because ids
carry no game meaning beyond tie-breaking `attack` between equal-hp monsters.

`tests/test_roundtrip.py` checks the three agree on one state from each of
seeds 0-99, on every state of 30 noisy-oracle episodes (covering damaged
monsters, every last action and the won state with the player on the goal),
and on a 13x7 map with three hp-3 monsters at tile 24.

## Acceptance Criteria
- **Given** 100 seeded observations **when** rendered to text and to image and decoded **then** all three agree.
