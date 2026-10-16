"""Fake backend (story 3.2): the oracle with controllable noise, for CI and harness tests.

It sees only the wire request (ADR-0002): it parses the state text back into
an observation (:func:`~gridworld.render.text.parse_text`; in image mode the
text block) and asks :func:`~gridworld.oracle.oracle`. With probability
``noise`` it answers a uniformly random *other* action instead.

Probabilities look like a model's: the chosen action gets a seeded draw in
[0.6, 0.95]; the other five share the remainder equally. ``usage`` estimates
``input_tokens`` as ``len(prefix + state text) // 4``, ``output_tokens`` 0.
``timing_ms.total`` reports exactly ``latency_s`` (the call sleeps that long),
so timing tests are deterministic. ``noul`` questions are answered with
``noul`` (a constant P(yes), or ``f(observation, question_name)``; default
0.1), which is how tests script System Two's pause_to_plan (story 5.2). When
a choice question offers ``plan`` (story 5.7's ``--think action``), its
probability is ``plan_p`` (a constant or ``f(observation)``; default 0.05),
the other options are scaled by ``1 - plan_p``, and ``plan`` is the choice
when ``plan_p >= 0.5``. With ``prefix_cache=True`` it simulates a
delta prefix cache (what story 4.4's transcript mode needs from a real
server): ``cached_tokens`` is the common character prefix with the previous
request's ``prefix`` plus joined text, // 4, and ``input_tokens`` the rest,
matching the golden library's split of computed versus cached tokens. All randomness comes from one
``random.Random(seed)`` advanced per call: same seed and requests, same answers.
"""

from __future__ import annotations

import os
import random
import time
from collections.abc import Callable
from typing import Any

from ..oracle import oracle
from ..render.text import parse_text
from ..sim import Observation

__all__ = ["FakeBackend"]


def _state_text(state: Any) -> str:
    if isinstance(state, str):
        return state
    if isinstance(state, list):
        texts = [s for s in state if isinstance(s, str)]
        if texts:
            return texts[-1]
    raise ValueError("fake backend needs a text state (or a text block in a state list)")


class FakeBackend:
    """Oracle-plus-noise backend; ``noise=0`` agrees with the oracle on every tick."""

    def __init__(
        self,
        noise: float = 0.0,
        latency_s: float = 0.0,
        seed: int = 0,
        prefix_cache: bool = False,
        noul: Callable[[Observation, str], float] | float = 0.1,
        plan_p: Callable[[Observation], float] | float = 0.05,
    ) -> None:
        self.noul, self.plan_p = noul, plan_p
        if not 0.0 <= noise <= 1.0:
            raise ValueError("noise must be in [0, 1]")
        self.noise, self.latency_s, self.prefix_cache = noise, latency_s, prefix_cache
        self._previous = ""
        self.rng = random.Random(seed)
        self.id = f"fake(noise={noise:g})"

    def decide(self, request: dict[str, Any]) -> dict[str, Any]:
        text = _state_text(request["state"])
        obs = parse_text(text)
        best = oracle(obs)
        answers = {}
        for name, question in request["questions"].items():
            if question["type"] == "noul":
                p = self.noul(obs, name) if callable(self.noul) else self.noul
                answers[name] = {"type": "noul", "noul": float(p)}
                continue
            if question["type"] != "choice":
                continue
            options = [o for o in question["criteria"] if o != "plan"]
            pick = best.value if best.value in options else options[0]
            if self.rng.random() < self.noise:
                pick = self.rng.choice([o for o in options if o != pick])
            top = self.rng.uniform(0.6, 0.95)
            rest = (1.0 - top) / (len(options) - 1)
            probs = {o: (top if o == pick else rest) for o in options}
            if "plan" in question["criteria"]:
                pp = float(self.plan_p(obs) if callable(self.plan_p) else self.plan_p)
                probs = {o: v * (1.0 - pp) for o, v in probs.items()} | {"plan": pp}
                if pp >= 0.5:
                    pick = "plan"
                top = probs[pick]
            answers[name] = {
                "type": "choice",
                "choice": pick,
                "probabilities": probs,
                "confidence": top,
            }
        if self.latency_s > 0:
            time.sleep(self.latency_s)
        state = request["state"]
        texts = [s for s in state if isinstance(s, str)] if isinstance(state, list) else [text]
        full = request.get("prefix", "") + "\n".join(texts)
        usage = {"input_tokens": len(full) // 4, "output_tokens": 0}
        if self.prefix_cache:
            common = len(os.path.commonprefix([self._previous, full]))
            self._previous = full
            usage = {
                "input_tokens": (len(full) - common) // 4,
                "output_tokens": 0,
                "cached_tokens": common // 4,
            }
        return {
            "model": self.id,
            "answers": answers,
            "usage": usage,
            "timing_ms": {"total": self.latency_s * 1000},
        }
