"""Story 2.3 — decoders that invert the renderers (test code, not product code).

Each returns a :class:`Decoded`: the game state a renderer claims to carry.
Monster ids are not drawn in the image, so ``monsters`` is a set of
``(pos, hp)``; the text decoder also returns ``monster_ids``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from PIL import Image

from gridworld.render.text import GLYPHS
from gridworld.render.tiles import (
    ACTION_COLOURS,
    COLOURS,
    DIGITS,
    pip_layout,
    status_geometry,
)
from gridworld.sim import Action, Cell, Observation


@dataclass(frozen=True)
class Decoded:
    width: int
    height: int
    walls: frozenset[Cell]
    player: Cell
    goal: Cell
    monsters: frozenset[tuple[Cell, int]]
    player_hp: int
    tick: int
    last_action: Action | None
    monster_ids: tuple[int, ...] | None = field(default=None, compare=False)


def from_observation(obs: Observation) -> Decoded:
    return Decoded(
        width=obs.width,
        height=obs.height,
        walls=obs.walls,
        player=obs.player,
        goal=obs.goal,
        monsters=frozenset((m.pos, m.hp) for m in obs.monsters),
        player_hp=obs.player_hp,
        tick=obs.tick,
        last_action=obs.last_action,
        monster_ids=tuple(m.id for m in obs.monsters),
    )


_MAP = re.compile(r"^Map (\d+)x(\d+),")
_STATUS = re.compile(
    r"^Status: hp (\d+) \| tick (\d+) \| last (\w+) \| adjacent M: [^|]+ \| goal: ([\w-]+)"
    r" \| monsters: (.*)$"
)
_MONSTER = re.compile(r"M(\d+) \((\d+),(\d+)\) hp (\d+)")


def decode_text(text: str) -> Decoded:
    lines = text.split("\n")
    i = next(k for k, ln in enumerate(lines) if _MAP.match(ln))
    width, height = map(int, _MAP.match(lines[i]).groups())
    rows = [ln.lstrip().split(" ", 1)[1] for ln in lines[i + 2 : i + 2 + height]]
    assert all(len(r) == width for r in rows)
    cells = {(x, y): ch for y, r in enumerate(rows) for x, ch in enumerate(r)}
    find = lambda g: [c for c, ch in cells.items() if ch == GLYPHS[g]]
    (player,) = find("player")
    m = _STATUS.match(lines[-1])
    assert m, lines[-1]
    hp, tick, last, goal_hint, mlist = m.groups()
    goal = player if goal_hint == "here" else find("goal")[0]
    monsters = [tuple(map(int, g)) for g in _MONSTER.findall(mlist)]
    assert {(x, y) for _, x, y, _ in monsters} == set(find("monster"))
    return Decoded(
        width=width,
        height=height,
        walls=frozenset(find("wall")),
        player=player,
        goal=goal,
        monsters=frozenset(((x, y), h) for _, x, y, h in monsters),
        player_hp=int(hp),
        tick=int(tick),
        last_action=None if last == "none" else Action(last),
        monster_ids=tuple(mid for mid, *_ in monsters),
    )


def _read_digits(px, x0: int, y0: int, scale: int) -> str:
    out = ""
    while True:
        bits = tuple(
            "".join(
                "1" if px[x0 + c * scale, y0 + r * scale] == COLOURS["digit"] else "0"
                for c in range(3)
            )
            for r in range(5)
        )
        match = [d for d, pattern in DIGITS.items() if pattern == bits]
        if not match:
            return out
        out += match[0]
        x0 += 4 * scale


def decode_image(img: Image.Image, tile: int = 16) -> Decoded:
    px = img.load()
    width, height = img.width // tile, (img.height - 2 * tile) // tile
    by_colour = {
        v: k for k, v in COLOURS.items() if k in ("floor", "wall", "goal", "player", "monster")
    }
    walls, monsters, player, goal = set(), set(), None, None
    size, pitch, capacity = pip_layout(tile)
    for y in range(height):
        for x in range(width):
            x0, y0 = x * tile, y * tile
            kind = by_colour[px[x0 + tile // 2, y0 + tile // 2]]
            if kind == "wall":
                walls.add((x, y))
            elif kind == "goal":
                goal = (x, y)
            elif kind == "player":
                player = (x, y)
                if by_colour[px[x0 + 1, y0 + tile // 2]] == "goal":
                    goal = (x, y)
            elif kind == "monster":
                hp = sum(
                    px[x0 + pitch // 2 + i * pitch, y0 + size] == COLOURS["pip"]
                    for i in range(capacity)
                )
                monsters.add(((x, y), hp))
    g = status_geometry(img.width, tile)
    sy = height * tile
    hp = 0
    while (
        2 + hp * g["hp_pitch"] < img.width
        and px[2 + hp * g["hp_pitch"], sy + g["hp_y"]] == COLOURS["hp"]
    ):
        hp += 1
    tick = _read_digits(px, 2, sy + g["digit_y"], g["digit_scale"])
    swatch = px[g["swatch_x"] + 1, sy + tile + 3]
    last = next((a for a, c in ACTION_COLOURS.items() if c == swatch), None)
    return Decoded(
        width=width,
        height=height,
        walls=frozenset(walls),
        player=player,
        goal=goal,
        monsters=frozenset(monsters),
        player_hp=hp,
        tick=int(tick),
        last_action=last,
    )
