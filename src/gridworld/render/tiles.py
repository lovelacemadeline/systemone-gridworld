"""Shared tile code (story 2.2): the only place map pixels are drawn.

Both :func:`gridworld.render.image.to_image` and the live view
(:mod:`gridworld.view`, which blits the PIL image) go through these functions,
so the window and the PNG a vision backend sees cannot drift (ADR-0001).

Everything is axis-aligned rectangles in flat colours (no anti-aliasing, no
fonts), so output is byte-identical across runs and platforms, and a decoder
can recover the state by sampling pixels:

- a cell's **kind** is the colour of its centre pixel; the player is an inner
  square whose border (sample ``(1, tile // 2)`` within the cell) keeps the
  colour of the cell beneath — floor, or goal when standing on it;
- a **monster's hp** is the number of white pips along its tile's top edge;
- the **status strip** holds player hp as red pips, the tick as 3x5 bitmap
  digits, and the last action as a colour swatch at the right end.
"""

from __future__ import annotations

from PIL import ImageDraw

from ..sim import Action

__all__ = [
    "ACTION_COLOURS",
    "COLOURS",
    "DIGITS",
    "draw_digits",
    "draw_status",
    "draw_tile",
    "pip_layout",
    "status_geometry",
]

RGB = tuple[int, int, int]

COLOURS: dict[str, RGB] = {
    "floor": (232, 230, 218),
    "wall": (64, 64, 76),
    "goal": (60, 176, 80),
    "player": (40, 92, 220),
    "monster": (204, 44, 44),
    "pip": (255, 255, 255),
    "strip": (28, 28, 32),
    "hp": (232, 72, 72),
    "digit": (240, 240, 240),
}

ACTION_COLOURS: dict[Action, RGB] = {
    Action.NORTH: (250, 200, 40),
    Action.SOUTH: (40, 200, 220),
    Action.EAST: (200, 90, 220),
    Action.WEST: (250, 130, 40),
    Action.ATTACK: (255, 40, 120),
    Action.WAIT: (150, 150, 150),
}

# 3x5 bitmap digits, rows top to bottom, "1" = lit.
DIGITS: dict[str, tuple[str, ...]] = {
    "0": ("111", "101", "101", "101", "111"),
    "1": ("010", "110", "010", "010", "111"),
    "2": ("111", "001", "111", "100", "111"),
    "3": ("111", "001", "111", "001", "111"),
    "4": ("101", "101", "111", "001", "001"),
    "5": ("111", "100", "111", "001", "111"),
    "6": ("111", "100", "111", "101", "111"),
    "7": ("111", "001", "001", "001", "001"),
    "8": ("111", "101", "111", "101", "111"),
    "9": ("111", "101", "111", "001", "111"),
}


def _rect(draw: ImageDraw.ImageDraw, x0: int, y0: int, w: int, h: int, colour: RGB) -> None:
    draw.rectangle((x0, y0, x0 + w - 1, y0 + h - 1), fill=colour)


def pip_layout(tile: int) -> tuple[int, int, int]:
    """``(size, pitch, capacity)`` of the hp pips drawn along a monster tile's top edge."""
    size = max(1, tile // 8)
    pitch = size * 2
    return size, pitch, max(1, (tile - pitch) // pitch)


def draw_tile(
    draw: ImageDraw.ImageDraw,
    kind: str,
    cx: int,
    cy: int,
    tile: int,
    *,
    under: str = "floor",
    hp: int | None = None,
) -> None:
    """Draw cell ``(cx, cy)`` as ``kind`` (floor, wall, goal, player, monster).

    ``under`` is what the player stands on (``floor`` or ``goal``); it shows as
    the player tile's border. ``hp`` (monsters only) draws that many pips.
    """
    x0, y0 = cx * tile, cy * tile
    if kind == "player":
        _rect(draw, x0, y0, tile, tile, COLOURS[under])
        inset = tile // 4
        _rect(draw, x0 + inset, y0 + inset, tile - 2 * inset, tile - 2 * inset, COLOURS["player"])
        return
    _rect(draw, x0, y0, tile, tile, COLOURS[kind])
    if kind == "monster" and hp:
        size, pitch, capacity = pip_layout(tile)
        if hp > capacity:
            raise ValueError(f"monster hp {hp} exceeds {capacity} pips at tile {tile}")
        for i in range(hp):
            _rect(draw, x0 + pitch // 2 + i * pitch, y0 + size, size, size, COLOURS["pip"])


def draw_digits(draw: ImageDraw.ImageDraw, text: str, x0: int, y0: int, scale: int) -> int:
    """Draw decimal ``text`` with :data:`DIGITS` at ``scale`` px per bit; return the end x."""
    for ch in text:
        for r, bits in enumerate(DIGITS[ch]):
            for c, bit in enumerate(bits):
                if bit == "1":
                    _rect(draw, x0 + c * scale, y0 + r * scale, scale, scale, COLOURS["digit"])
        x0 += 4 * scale
    return x0


def status_geometry(width_px: int, tile: int) -> dict[str, int]:
    """Pixel layout of the status strip, shared by the renderer and decoders."""
    return {
        "hp_size": max(2, tile // 2),
        "hp_pitch": max(2, tile // 2) + 2,
        "hp_y": 2,
        "digit_scale": max(1, tile // 8),
        "digit_y": tile + 2,
        "swatch": tile - 4,
        "swatch_x": width_px - tile + 2,
    }


def draw_status(
    draw: ImageDraw.ImageDraw,
    y0: int,
    width_px: int,
    tile: int,
    *,
    hp: int,
    tick: int,
    last_action: Action | None,
) -> None:
    """Draw the ``2 * tile`` px status strip whose top edge is at ``y0``."""
    g = status_geometry(width_px, tile)
    _rect(draw, 0, y0, width_px, 2 * tile, COLOURS["strip"])
    if hp * g["hp_pitch"] > width_px:
        raise ValueError(f"hp {hp} does not fit a {width_px} px status strip")
    for i in range(hp):
        _rect(
            draw, 2 + i * g["hp_pitch"], y0 + g["hp_y"], g["hp_size"], g["hp_size"], COLOURS["hp"]
        )
    draw_digits(draw, str(tick), 2, y0 + g["digit_y"], g["digit_scale"])
    if last_action is not None:
        s = g["swatch"]
        _rect(draw, g["swatch_x"], y0 + tile + 2, s, s, ACTION_COLOURS[last_action])
