"""Story 2.2 — image renderer and the shared tile code."""

from __future__ import annotations

import hashlib
import io

import pytest
from PIL import Image

from gridworld.render.image import image_size, to_image, to_png
from gridworld.render.tiles import ACTION_COLOURS, COLOURS
from gridworld.sim import Action, WorldConfig, generate_map

# sha256 of to_image(generate_map(3)).tobytes() at tile 16. A change here is a
# change to what vision backends see: update it deliberately, never casually.
PINNED_SEED_3 = "cbb3ab0b703b2e6f68c97505540797186e0499aa9c4c2a5f03095c8abfc79f26"


def raw_hash(img: Image.Image) -> str:
    return hashlib.sha256(img.tobytes()).hexdigest()


def test_size_is_map_plus_a_two_tile_status_strip():
    obs = generate_map(0, WorldConfig(width=12, height=7))
    assert to_image(obs, tile=16).size == (12 * 16, 7 * 16 + 32) == image_size(obs, 16)
    assert to_image(obs, tile=10).size == (120, 90)


def test_renders_identically_across_runs():
    for seed in range(10):
        obs = generate_map(seed)
        assert to_png(obs) == to_png(obs)
    assert raw_hash(to_image(generate_map(3))) == PINNED_SEED_3


def test_png_decodes_to_the_same_pixels():
    obs = generate_map(5)
    img = Image.open(io.BytesIO(to_png(obs)))
    assert img.mode == "RGB" and img.tobytes() == to_image(obs).tobytes()


def test_cells_draw_in_their_tile_colours(make_obs):
    obs = make_obs(player=(1, 0), goal=(4, 4), walls=[(0, 0)], monsters=[((3, 2), 2)])
    img, t = to_image(obs), 16
    centre = lambda x, y: img.getpixel((x * t + t // 2, y * t + t // 2))
    assert centre(0, 0) == COLOURS["wall"]
    assert centre(1, 0) == COLOURS["player"]
    assert centre(3, 2) == COLOURS["monster"]
    assert centre(4, 4) == COLOURS["goal"]
    assert centre(2, 2) == COLOURS["floor"]


def test_status_strip_shows_last_action_swatch(make_obs):
    obs = make_obs().model_copy(update={"last_action": Action.ATTACK})
    img = to_image(obs)
    assert img.getpixel((img.width - 8, img.height - 8)) == ACTION_COLOURS[Action.ATTACK]


def test_monster_hp_beyond_pip_capacity_raises(make_obs):
    with pytest.raises(ValueError, match="pips"):
        to_image(make_obs(monsters=[((0, 0), 99)]))
