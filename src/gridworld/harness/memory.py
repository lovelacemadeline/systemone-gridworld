"""Memory modes (story 4.4): what a request carries besides the current observation.

A :class:`Memory` is consulted once per tick by the loop:

- :meth:`Memory.tail` — text appended to the status line (``summary`` mode),
  passed to :func:`~gridworld.backends.request.build_request` as
  ``memory_tail``; ``None`` for none;
- :meth:`Memory.history` — prior turns for a multi-turn ``state`` list
  (``transcript`` mode); empty otherwise;
- :meth:`Memory.observe` — told what happened after each decision.

``none`` is the Markov baseline: every tick is a fresh request.
"""

from __future__ import annotations

from typing import Protocol

from ..sim import Action, Observation

__all__ = [
    "MEMORY_MODES",
    "Memory",
    "NoMemory",
    "SummaryMemory",
    "TranscriptMemory",
    "make_memory",
]


class Memory(Protocol):
    name: str

    def reset(self) -> None: ...

    def tail(self, obs: Observation) -> str | None: ...

    def history(self) -> list[str]: ...

    def observe(self, obs: Observation, text: str, action: Action, after: Observation) -> None: ...


class NoMemory:
    """Current observation only (the baseline)."""

    name = "none"

    def reset(self) -> None:
        pass

    def tail(self, obs: Observation) -> str | None:
        return None

    def history(self) -> list[str]:
        return []

    def observe(self, obs: Observation, text: str, action: Action, after: Observation) -> None:
        pass


class SummaryMemory:
    """The last ``k`` actions and resulting cells, appended to the status line.

    Renders as ``recent: east->(3,4), east->(4,4), north->(4,3)`` (oldest
    first; ``recent: none`` on the first tick). Bounded tokens, still one fresh
    request per tick, and only the status line differs from ``none``.
    """

    name = "summary"

    def __init__(self, k: int = 3) -> None:
        self.k = k
        self._recent: list[tuple[Action, tuple[int, int]]] = []

    def reset(self) -> None:
        self._recent = []

    def tail(self, obs: Observation) -> str | None:
        if not self._recent:
            return "recent: none"
        return "recent: " + ", ".join(f"{a.value}->({x},{y})" for a, (x, y) in self._recent)

    def history(self) -> list[str]:
        return []

    def observe(self, obs: Observation, text: str, action: Action, after: Observation) -> None:
        self._recent = [*self._recent, (action, after.player)][-self.k :]


class TranscriptMemory:
    """A growing conversation: every prior tick's state, the question and the chosen label.

    Each prior turn is ``<state text>\nWhich action next? <action>``; the
    request's ``state`` is the list of prior turns plus the current state text.
    Unbounded, so it is only cheap on a backend whose prefix cache hits on the
    longest common token prefix (the golden server's delta prefix caching,
    not yet landed); the loop records ``cached_tokens`` per tick to show it.
    """

    name = "transcript"

    def __init__(self) -> None:
        self._turns: list[str] = []

    def reset(self) -> None:
        self._turns = []

    def tail(self, obs: Observation) -> str | None:
        return None

    def history(self) -> list[str]:
        return list(self._turns)

    def observe(self, obs: Observation, text: str, action: Action, after: Observation) -> None:
        self._turns.append(f"{text}\nWhich action next? {action.value}")


MEMORY_MODES: dict[str, type] = {
    "none": NoMemory,
    "summary": SummaryMemory,
    "transcript": TranscriptMemory,
}


def make_memory(name: str) -> Memory:
    """Build a memory mode by name (see :data:`MEMORY_MODES`)."""
    try:
        return MEMORY_MODES[name]()
    except KeyError:
        raise ValueError(f"unknown memory {name!r}; choose from {sorted(MEMORY_MODES)}") from None
