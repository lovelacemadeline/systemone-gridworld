"""Text renderer (story 2.1): the observation as prompt text, stable parts first.

Layout, top to bottom::

    <legend: three fixed lines>
    Map 10x10, x across (0-9), y down (0-9):
       0123456789
     0 #.#.......
     ...
     9 ...#......
    Status: hp 6 | tick 3 | last east | adjacent M: north | goal: south-east | monsters: M0 (4,7) hp 2, M1 (1,8) hp 1

Everything above the status line depends only on the map and the cells of
the player, goal and monsters, so consecutive ticks share the longest possible
prefix (prefix caching): a move changes exactly the two map characters it
vacates and enters, plus the status line. The status line is always last and
is the only line that carries hp, tick and last action.

Map glyphs: ``#`` wall, ``.`` floor, ``@`` player, ``G`` goal, ``M`` monster.
The column header is ``x % 10`` so rows stay fixed width on any map size. When
the player stands on the goal (a won terminal state) the cell shows ``@`` and
the status line says ``goal: here``.

Lossless (ADR-0001): width, height, walls, player, goal, monsters (id, cell,
hp), player hp, tick and last action are all recoverable from the text. The
seed and the reserved ``items`` field are not rendered.
"""

from __future__ import annotations

import re

from ..sim import MOVES, Action, Cell, Monster, Observation, adjacent

__all__ = ["GLYPHS", "LEGEND", "compass", "parse_text", "status_line", "to_text"]

GLYPHS = {"wall": "#", "floor": ".", "player": "@", "goal": "G", "monster": "M"}

LEGEND = (
    "Gridworld. You are @ and must reach G. M is a monster; # is a wall; . is floor.\n"
    "Moves: north = y-1 (up), south = y+1 (down), east = x+1 (right), west = x-1 (left).\n"
    "attack hits one adjacent M for 1 damage; wait does nothing. Adjacent M hit you for 1 per tick."
)

_DIRECTION = {delta: action.value for action, delta in MOVES.items()}


def compass(frm: Cell, to: Cell) -> str:
    """Direction from ``frm`` to ``to``: ``north``, ``south-east``, ... or ``here``."""
    dx, dy = to[0] - frm[0], to[1] - frm[1]
    ns = "north" if dy < 0 else "south" if dy > 0 else ""
    ew = "west" if dx < 0 else "east" if dx > 0 else ""
    return "-".join(p for p in (ns, ew) if p) or "here"


def _map_lines(obs: Observation) -> list[str]:
    monsters = {m.pos for m in obs.monsters}
    pad = len(str(obs.height - 1))
    header = " " * (pad + 1) + "".join(str(x % 10) for x in range(obs.width))
    rows = [header]
    for y in range(obs.height):
        row = []
        for x in range(obs.width):
            c = (x, y)
            if c == obs.player:
                g = GLYPHS["player"]
            elif c in monsters:
                g = GLYPHS["monster"]
            elif c == obs.goal:
                g = GLYPHS["goal"]
            elif c in obs.walls:
                g = GLYPHS["wall"]
            else:
                g = GLYPHS["floor"]
            row.append(g)
        rows.append(f"{y:>{pad}} " + "".join(row))
    return rows


def status_line(obs: Observation) -> str:
    """The single volatile line: hp, tick, last action, threats, goal hint, monster list."""
    near = [
        _DIRECTION[(m.pos[0] - obs.player[0], m.pos[1] - obs.player[1])]
        for m in obs.monsters
        if adjacent(m.pos, obs.player)
    ]
    monsters = ", ".join(f"M{m.id} ({m.pos[0]},{m.pos[1]}) hp {m.hp}" for m in obs.monsters)
    last = obs.last_action.value if obs.last_action is not None else "none"
    return (
        f"Status: hp {obs.player_hp} | tick {obs.tick} | last {last}"
        f" | adjacent M: {', '.join(near) or 'none'}"
        f" | goal: {compass(obs.player, obs.goal)}"
        f" | monsters: {monsters or 'none'}"
    )


def to_text(obs: Observation) -> str:
    """Render ``obs`` as prompt text: legend, map, then one status line (no trailing newline)."""
    head = (
        f"Map {obs.width}x{obs.height}, x across (0-{obs.width - 1}), y down (0-{obs.height - 1}):"
    )
    return "\n".join([LEGEND, head, *_map_lines(obs), status_line(obs)])


_MAP_HEAD = re.compile(r"^Map (\d+)x(\d+),")
_STATUS = re.compile(
    r"^Status: hp (\d+) \| tick (\d+) \| last (\w+) \| adjacent M: [^|]+ \| goal: ([\w-]+)"
    r" \| monsters: (.*)$"
)
_MONSTER = re.compile(r"M(\d+) \((\d+),(\d+)\) hp (\d+)")


def parse_text(text: str) -> Observation:
    """Invert :func:`to_text`; a memory tail on the status line or later lines is ignored.

    For backends that must act from the rendered state alone (ADR-0002), such
    as the fake backend. The seed is not rendered, so it comes back as 0.
    Raises ``ValueError`` on text that is not a rendered observation.
    """
    lines = text.split("\n")
    try:
        i = next(k for k, ln in enumerate(lines) if _MAP_HEAD.match(ln))
        width, height = map(int, _MAP_HEAD.match(lines[i]).groups())
        rows = [ln.lstrip().split(" ", 1)[1] for ln in lines[i + 2 : i + 2 + height]]
        status = _STATUS.match(lines[i + 2 + height])
    except (StopIteration, IndexError) as exc:
        raise ValueError("not a rendered observation") from exc
    if status is None or len(rows) != height or any(len(r) != width for r in rows):
        raise ValueError("not a rendered observation")
    cells = {(x, y): ch for y, row in enumerate(rows) for x, ch in enumerate(row)}
    walls = frozenset(c for c, ch in cells.items() if ch == GLYPHS["wall"])
    (player,) = [c for c, ch in cells.items() if ch == GLYPHS["player"]]
    hp, tick, last, goal_hint, mlist = status.groups()
    goal = (
        player
        if goal_hint == "here"
        else next(c for c, ch in cells.items() if ch == GLYPHS["goal"])
    )
    monsters = tuple(
        Monster(id=int(i), pos=(int(x), int(y)), hp=int(h))
        for i, x, y, h in _MONSTER.findall(mlist)
    )
    return Observation(
        width=width,
        height=height,
        walls=walls,
        player=player,
        goal=goal,
        monsters=monsters,
        player_hp=int(hp),
        tick=int(tick),
        last_action=None if last == "none" else Action(last),
        seed=0,
    )
