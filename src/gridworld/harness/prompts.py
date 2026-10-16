"""The default rules prefix (story 4.1): stable text sent as the request ``prefix``.

It is identical on every tick, so a backend with prefix caching (the golden
server, :class:`~gridworld.backends.local.LocalBackend`) prefills it once.
``gridworld play --prefix FILE`` replaces it; :func:`load_prefix` reads that.
"""

from __future__ import annotations

from pathlib import Path

__all__ = ["DEFAULT_PREFIX", "load_prefix"]

DEFAULT_PREFIX = """\
You are playing a turn-based grid game, one decision per turn.

Each turn you see a legend, the map, and one status line. On the map, @ is you, \
G is the goal, M is a monster, # is a wall and . is open floor. x grows to the right \
(east) and y grows downward (south), so north is y - 1.

Rules:
- Moving into a wall, the edge of the map, or a monster does nothing (the turn still passes).
- attack hits one monster next to you (not diagonal) for 1 damage; at 0 hp it is removed.
- At the end of every turn, each monster next to you hits you for 1. At 0 hp you lose.
- Monsters that can see you (within 4 steps) move one step toward you each turn.
- Reach G to win. You lose if you have not reached it in 200 turns.

Good play: head for the goal along the shortest safe path; fight a monster that is \
already next to you when you can win the exchange; avoid stepping next to monsters \
when there is another way.

Answer with exactly one action."""


def load_prefix(path: str | Path | None) -> str:
    """The prefix text: the file at ``path`` (trailing whitespace stripped) or the default."""
    if path is None:
        return DEFAULT_PREFIX
    return Path(path).read_text(encoding="utf-8").rstrip()
