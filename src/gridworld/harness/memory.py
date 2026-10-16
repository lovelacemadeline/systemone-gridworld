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

__all__ = ["MEMORY_MODES", "Memory", "NoMemory", "make_memory"]


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


MEMORY_MODES: dict[str, type] = {"none": NoMemory}


def make_memory(name: str) -> Memory:
    """Build a memory mode by name (see :data:`MEMORY_MODES`)."""
    try:
        return MEMORY_MODES[name]()
    except KeyError:
        raise ValueError(f"unknown memory {name!r}; choose from {sorted(MEMORY_MODES)}") from None
