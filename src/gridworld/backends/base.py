"""The backend protocol (story 3.1, ADR-0002): a wire request dict in, a wire response out."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

__all__ = ["Backend"]


@runtime_checkable
class Backend(Protocol):
    """Anything that answers a ``SystemOneRequest``-shaped dict.

    ``id`` names the backend in recordings and reports. ``decide`` must not rely
    on anything outside the request (no sim internals): call it through
    :func:`gridworld.backends.adapter.call`, which validates both directions.
    """

    id: str

    def decide(self, request: dict[str, Any]) -> dict[str, Any]: ...
