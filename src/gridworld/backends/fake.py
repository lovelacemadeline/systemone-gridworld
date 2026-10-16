"""Fake backend (story 3.2): the oracle with controllable noise, for CI and harness tests.

It sees only the wire request (ADR-0002): it parses the state text back into
an observation (:func:`~gridworld.render.text.parse_text`; in image mode the
text block) and asks :func:`~gridworld.oracle.oracle`. With probability
``noise`` it answers a uniformly random *other* action instead.

Probabilities look like a model's: the chosen action gets a seeded draw in
[0.6, 0.95]; the other five share the remainder equally. ``usage`` estimates
``input_tokens`` as ``len(prefix + state text) // 4``, ``output_tokens`` 0.
``timing_ms.total`` reports exactly ``latency_s`` (the call sleeps that long),
so timing tests are deterministic. All randomness comes from one
``random.Random(seed)`` advanced per call: same seed and requests, same answers.
"""

from __future__ import annotations

import random
import time
from typing import Any

from ..oracle import oracle
from ..render.text import parse_text

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

    def __init__(self, noise: float = 0.0, latency_s: float = 0.0, seed: int = 0) -> None:
        if not 0.0 <= noise <= 1.0:
            raise ValueError("noise must be in [0, 1]")
        self.noise, self.latency_s = noise, latency_s
        self.rng = random.Random(seed)
        self.id = f"fake(noise={noise:g})"

    def decide(self, request: dict[str, Any]) -> dict[str, Any]:
        text = _state_text(request["state"])
        best = oracle(parse_text(text))
        answers = {}
        for name, question in request["questions"].items():
            if question["type"] != "choice":
                continue
            options = list(question["criteria"])
            pick = best.value if best.value in options else options[0]
            if self.rng.random() < self.noise:
                pick = self.rng.choice([o for o in options if o != pick])
            top = self.rng.uniform(0.6, 0.95)
            rest = (1.0 - top) / (len(options) - 1)
            probs = {o: (top if o == pick else rest) for o in options}
            answers[name] = {
                "type": "choice",
                "choice": pick,
                "probabilities": probs,
                "confidence": top,
            }
        if self.latency_s > 0:
            time.sleep(self.latency_s)
        n_chars = len(request.get("prefix", "")) + len(text)
        return {
            "model": self.id,
            "answers": answers,
            "usage": {"input_tokens": n_chars // 4, "output_tokens": 0},
            "timing_ms": {"total": self.latency_s * 1000},
        }
