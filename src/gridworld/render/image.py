"""Image renderer (story 2.2): the observation as a small RGB image / PNG.

The image is ``width * tile`` by ``height * tile + 2 * tile`` pixels: the map,
then a status strip (player hp pips, tick digits, last-action swatch). All
drawing goes through :mod:`gridworld.render.tiles`, the same code the live view
shows. Lossless with respect to the text view (ADR-0001, story 2.3): walls,
player, goal, monsters with hp, player hp, tick and last action decode back by
pixel sampling. Monster ids, the seed and ``items`` are not drawn.
"""

from __future__ import annotations

import io

from PIL import Image, ImageDraw

from ..sim import Observation
from .tiles import COLOURS, draw_status, draw_tile

__all__ = ["image_size", "to_image", "to_png"]


def image_size(obs: Observation, tile: int = 16) -> tuple[int, int]:
    """``(width_px, height_px)`` of :func:`to_image` for ``obs``."""
    return obs.width * tile, obs.height * tile + 2 * tile


def to_image(obs: Observation, tile: int = 16) -> Image.Image:
    """Render ``obs`` as an RGB :class:`PIL.Image.Image` (pure, deterministic pixels)."""
    if tile < 8:
        raise ValueError("tile must be at least 8 px")
    img = Image.new("RGB", image_size(obs, tile), COLOURS["floor"])
    draw = ImageDraw.Draw(img)
    for x, y in obs.walls:
        draw_tile(draw, "wall", x, y, tile)
    draw_tile(draw, "goal", *obs.goal, tile)
    for m in obs.monsters:
        draw_tile(draw, "monster", *m.pos, tile, hp=m.hp)
    under = "goal" if obs.player == obs.goal else "floor"
    draw_tile(draw, "player", *obs.player, tile, under=under)
    draw_status(
        draw,
        obs.height * tile,
        obs.width * tile,
        tile,
        hp=obs.player_hp,
        tick=obs.tick,
        last_action=obs.last_action,
    )
    return img


def to_png(obs: Observation, tile: int = 16) -> bytes:
    """:func:`to_image` encoded as PNG bytes (what a vision backend receives)."""
    buf = io.BytesIO()
    to_image(obs, tile).save(buf, format="PNG", optimize=False)
    return buf.getvalue()
