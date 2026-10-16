"""The validating adapter (story 3.1): the only way the harness talks to a backend.

:func:`call` validates the request, calls the backend on a deep copy (so a
backend cannot mutate the caller's request), measures wall time, validates the
response, then checks the parts the schema cannot express: the ``action``
answer exists, is a ``choice``, picks one of the offered actions (the
question's ``criteria``; all six unless the request is legal-only), and gives a
probability for each of them. Under ``--think action`` (story 5.7) the
criteria also hold :data:`~gridworld.backends.request.PLAN_OPTION`: its
probability is ``Decision.plan_p`` (not in ``probabilities``), and when it is
the choice, ``Decision.chose_plan`` is set and ``action`` is the most likely
real action (what a caller that ignores the request to plan would step). Any failure raises :class:`SchemaError` or
:class:`BackendError` — a drifting backend fails loudly, never silently.
"""

from __future__ import annotations

import copy
import time
from typing import Any

from pydantic import BaseModel, ConfigDict

from ..sim import Action
from .base import Backend
from .request import PLAN_OPTION, QUESTION
from .schema import validate_request, validate_response

__all__ = ["BackendError", "Decision", "call"]


class BackendError(ValueError):
    """A schema-valid response that does not answer the action question properly."""


class Decision(BaseModel):
    """One answered tick: what to step, how sure, what it cost.

    ``probabilities`` covers the offered actions only (all six by default);
    ``plan_p`` is P(plan) when the plan option was offered (story 5.7).
    """

    model_config = ConfigDict(frozen=True)

    backend: str
    action: Action
    probabilities: dict[Action, float]
    confidence: float
    usage: dict[str, int]
    timing_ms: dict[str, float] | None
    wall_ms: float
    response: dict[str, Any]
    plan_p: float | None = None
    chose_plan: bool = False


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
    names = list(request["questions"][question]["criteria"])
    if answer["choice"] not in names:
        raise BackendError(f"{backend.id}: choice {answer['choice']!r} is not one of {names}")
    probs = answer["probabilities"]
    if sorted(probs) != sorted(names):
        raise BackendError(f"{backend.id}: probabilities cover {sorted(probs)}, expected {names}")
    actions = [k for k in names if k != PLAN_OPTION]
    probabilities = {Action(k): float(probs[k]) for k in actions}
    chose_plan = answer["choice"] == PLAN_OPTION
    action = (
        max(probabilities, key=probabilities.__getitem__)
        if chose_plan
        else Action(answer["choice"])
    )
    return Decision(
        backend=backend.id,
        action=action,
        probabilities=probabilities,
        plan_p=float(probs[PLAN_OPTION]) if PLAN_OPTION in names else None,
        chose_plan=chose_plan,
        confidence=float(answer["confidence"]),
        usage=dict(response["usage"]),
        timing_ms=response.get("timing_ms"),
        wall_ms=wall_ms,
        response=response,
    )
