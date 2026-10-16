"""Plan consumption (story 5.8): the plan's ``Route:`` line as moves, walked tick by tick.

A plan is free text, but the plan prompt asks for "route as a list of moves",
and models write a line such as ``Route: north, north, east x4, then north``.
:func:`parse_route` turns that line into a list of :class:`~gridworld.sim.Action`
values, tolerantly: commas, semicolons, arrows, ``then`` / ``and``, any case,
counts as ``x4`` / ``×4`` / ``4x`` / ``4 times`` / ``east 4`` / ``twice`` and
small number words. Anything that is not a move is ignored; a plan without a
``Route:`` line (or with nothing parseable on it) has no route.

:class:`RouteTracker` walks the route against the actions actually taken: a
taken action equal to the next move consumes it; ``deviation_limit``
consecutive non-matching actions mark the route ``deviated``; consuming the
last move marks it ``exhausted``. :func:`plan_for_tail` rewrites the plan's
route line as the remaining moves (``remaining route: east, east.``), so the
memory tail never tells the decider to make moves it has already made.

:func:`strip_action_line` drops a trailing ``Action: ...`` line, which a
planner writes when its generation runs on into answering the action question.
"""

from __future__ import annotations

import re
from typing import Literal

from ..sim import Action

__all__ = [
    "DEFAULT_DEVIATION_LIMIT",
    "RouteState",
    "RouteTracker",
    "find_route",
    "parse_route",
    "plan_for_tail",
    "strip_action_line",
]

DEFAULT_DEVIATION_LIMIT = 2
MAX_COUNT = 20  # a single "x99" is a typo, not a route

RouteState = Literal["active", "exhausted", "deviated"]

#: ``Route:`` (optionally bolded) up to the end of its line or the next ``Label:``.
_ROUTE = re.compile(
    r"[*_]*\b(?i:route)\b[*_]*\s*:[*_]*(?P<body>[^\n]*?)(?=\n|\s[A-Z][A-Za-z ]{0,20}:|$)"
)
_ACTION_LINE = re.compile(r"\n?[ \t]*[*_]*action[*_]*\s*:[^\n]*\s*\Z", re.IGNORECASE)
_WORDS = {
    "once": "1 times",
    "twice": "2 times",
    "thrice": "3 times",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
}
_DIR = "|".join(a.value for a in Action)
_MOVE = re.compile(
    rf"(?:\b(?P<lead>\d+)\s*(?:x|×|times)?\s+(?:steps?\s+|moves?\s+)?)?"
    rf"\b(?P<dir>{_DIR})(?:s|ward|wards)?\b"
    rf"(?:\s*(?:x|×|\*)\s*(?P<mul>\d+)\b|\s*\(\s*(?P<par>\d+)\s*\)|\s+(?P<tail>\d+)(?:\s*(?:times|x|×))?\b)?"
)


def strip_action_line(text: str) -> str:
    """``text`` without a trailing ``Action: ...`` line (the record keeps the original)."""
    return _ACTION_LINE.sub("", text).rstrip()


def find_route(text: str) -> re.Match[str] | None:
    """The first ``Route:`` span in ``text`` (group ``body`` is the move list)."""
    return _ROUTE.search(text)


def parse_route(text: str) -> list[Action]:
    """The moves on ``text``'s ``Route:`` line; ``[]`` when there is none."""
    m = find_route(text)
    return _parse_moves(m.group("body")) if m else []


def _parse_moves(body: str) -> list[Action]:
    s = body.lower()
    s = re.sub(r"\b(" + "|".join(_WORDS) + r")\b", lambda w: _WORDS[w.group(1)], s)
    moves: list[Action] = []
    for m in _MOVE.finditer(s):
        raw = m.group("mul") or m.group("par") or m.group("tail") or m.group("lead") or "1"
        moves += [Action(m.group("dir"))] * max(1, min(int(raw), MAX_COUNT))
    return moves


def plan_for_tail(text: str, remaining: list[Action]) -> str:
    """``text`` with its route line replaced by ``remaining route: <moves>.``."""
    m = find_route(text)
    if not m:
        return text
    moves = ", ".join(a.value for a in remaining) or "none"
    return f"{text[: m.start()]}remaining route: {moves}.{text[m.end() :]}"


class RouteTracker:
    """Walks a parsed route against the actions taken, one tick at a time."""

    def __init__(self, moves: list[Action], deviation_limit: int = DEFAULT_DEVIATION_LIMIT):
        self.moves = list(moves)
        self.deviation_limit = deviation_limit
        self.done = 0
        self.misses = 0
        self.state: RouteState = "exhausted" if not self.moves else "active"

    @property
    def remaining(self) -> list[Action]:
        return self.moves[self.done :]

    def advance(self, action: Action | str) -> RouteState:
        """Account for the action taken this tick; returns the new state."""
        if self.state != "active":
            return self.state
        if Action(action) == self.moves[self.done]:
            self.done += 1
            self.misses = 0
            if self.done == len(self.moves):
                self.state = "exhausted"
        else:
            self.misses += 1
            if self.misses >= self.deviation_limit:
                self.state = "deviated"
        return self.state
