"""The validating adapter (story 3.1): the only way the harness talks to a backend.

:func:`call` validates the request, calls the backend on a deep copy (so a
backend cannot mutate the caller's request), measures wall time, validates the
response, then checks the parts the schema cannot express: the ``action``
answer exists, is a ``choice``, picks one of the six actions, and gives a
probability for each of them. Any failure raises :class:`SchemaError` or
:class:`BackendError` — a drifting backend fails loudly, never silently.
"""

from __future__ import annotations

import copy
import time
from typing import Any

from pydantic import BaseModel, ConfigDict

from ..sim import Action
from .base import Backend
from .request import QUESTION
from .schema import validate_request, validate_response

__all__ = ["BackendError", "Decision", "call"]


class BackendError(ValueError):
    """A schema-valid response that does not answer the action question properly."""


class Decision(BaseModel):
    """One answered tick: what to step, how sure, what it cost."""

    model_config = ConfigDict(frozen=True)

    backend: str
    action: Action
    probabilities: dict[Action, float]
    confidence: float
    usage: dict[str, int]
    timing_ms: dict[str, float] | None
    wall_ms: float
    response: dict[str, Any]


def call(backend: Backend, request: dict[str, Any], *, question: str = QUESTION) -> Decision:
    """Validate ``request``, ask ``backend``, validate and parse its answer to ``question``."""
    validate_request(request)
    t0 = time.perf_counter()
    response = backend.decide(copy.deepcopy(request))
    wall_ms = (time.perf_counter() - t0) * 1000
    validate_response(response)
    answer = response["answers"].get(question)
    if answer is None:
        raise BackendError(f"{backend.id}: response has no answer for {question!r}")
    if answer.get("type") != "choice":
        raise BackendError(
            f"{backend.id}: answer {question!r} is {answer.get('type')!r}, not choice"
        )
    names = [a.value for a in Action]
    if answer["choice"] not in names:
        raise BackendError(f"{backend.id}: choice {answer['choice']!r} is not one of {names}")
    probs = answer["probabilities"]
    if sorted(probs) != sorted(names):
        raise BackendError(f"{backend.id}: probabilities cover {sorted(probs)}, expected {names}")
    return Decision(
        backend=backend.id,
        action=Action(answer["choice"]),
        probabilities={Action(k): float(probs[k]) for k in names},
        confidence=float(answer["confidence"]),
        usage=dict(response["usage"]),
        timing_ms=response.get("timing_ms"),
        wall_ms=wall_ms,
        response=response,
    )
