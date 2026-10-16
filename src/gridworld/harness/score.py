"""Scoring (stories 4.1, 4.2): per-episode summaries and the run-level aggregate.

Definitions (all computed from the per-tick :class:`TickLog` list):

- ``agreement``: fraction of ticks whose action equals the oracle's action on
  the same observation.
- ``outcome``: ``won`` / ``died`` / ``timeout`` from the sim, or ``stopped`` /
  ``max_ticks`` when the harness cut the episode short.
- ``oracle_steps``: ticks the oracle needs to win the same seed (played
  separately); ``None`` if the oracle itself fails. ``steps_over_oracle`` is
  ``steps / oracle_steps`` for won episodes when the oracle also won.
- oscillation: ``distinct_cell_ratio`` = distinct player cells visited (start
  included) / steps, and ``reversals`` = ticks where the player returns to the
  cell it occupied two ticks earlier after having moved away.
- ``decisions_per_s`` = steps / summed ``total_ms``; latency percentiles are
  over per-tick ``total_ms`` and ``backend_ms``.
- tokens: ``input_tokens`` and ``cached_tokens`` from the backend's usage;
  ``tokens_per_observation`` is their sum (the golden library counts cached
  prefix tokens separately from computed ones).
- ``mean_top_probability``: mean of the largest probability per tick.
"""

from __future__ import annotations

from statistics import fmean

import numpy as np
from pydantic import BaseModel, ConfigDict

from ..sim import Action, Cell, Observation

__all__ = ["EpisodeSummary", "TickLog", "oscillation", "percentile", "summarize_episode"]

OUTCOMES = {"goal": "won", "dead": "died", "timeout": "timeout"}


class TickLog(BaseModel):
    """What the loop knows about one tick (the recorded tick line, plus the result)."""

    model_config = ConfigDict(frozen=True)

    observation: Observation
    action: Action
    oracle_action: Action
    probabilities: dict[Action, float]
    usage: dict[str, int]
    timing: dict[str, float]
    after: Observation


class EpisodeSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    seed: int
    outcome: str
    steps: int
    oracle_steps: int | None
    steps_over_oracle: float | None
    agreement: float
    distinct_cell_ratio: float
    reversals: int
    decisions_per_s: float | None
    p50_total_ms: float | None
    p95_total_ms: float | None
    p50_backend_ms: float | None
    p95_backend_ms: float | None
    mean_input_tokens: float | None
    mean_cached_tokens: float | None
    tokens_per_observation: float | None
    mean_top_probability: float | None
    record_path: str | None = None


def percentile(values: list[float], q: float) -> float | None:
    return float(np.percentile(values, q)) if values else None


def oscillation(cells: list[Cell]) -> tuple[float, int]:
    """``(distinct cells / steps, reversals)`` for a path of player cells, start first."""
    steps = len(cells) - 1
    if steps <= 0:
        return 0.0, 0
    reversals = sum(
        1 for t in range(2, len(cells)) if cells[t] == cells[t - 2] and cells[t] != cells[t - 1]
    )
    return len(set(cells)) / steps, reversals


def _mean(values: list[float]) -> float | None:
    return fmean(values) if values else None


def summarize_episode(
    seed: int,
    ticks: list[TickLog],
    reason: str,
    oracle_steps: int | None,
    record_path: str | None = None,
) -> EpisodeSummary:
    """Score one episode (see the module docstring for every definition)."""
    steps = len(ticks)
    outcome = OUTCOMES.get(reason, reason)
    cells = [ticks[0].observation.player] + [t.after.player for t in ticks] if ticks else []
    ratio, reversals = oscillation(cells)
    total = [t.timing["total_ms"] for t in ticks if "total_ms" in t.timing]
    backend = [t.timing["backend_ms"] for t in ticks if "backend_ms" in t.timing]
    inp = [t.usage.get("input_tokens", 0) for t in ticks if t.usage]
    cached = [t.usage.get("cached_tokens", 0) for t in ticks if t.usage]
    tops = [max(t.probabilities.values()) for t in ticks if t.probabilities]
    return EpisodeSummary(
        seed=seed,
        outcome=outcome,
        steps=steps,
        oracle_steps=oracle_steps,
        steps_over_oracle=(steps / oracle_steps if outcome == "won" and oracle_steps else None),
        agreement=(sum(t.action is t.oracle_action for t in ticks) / steps) if steps else 0.0,
        distinct_cell_ratio=ratio,
        reversals=reversals,
        decisions_per_s=(steps / (sum(total) / 1000)) if total and sum(total) > 0 else None,
        p50_total_ms=percentile(total, 50),
        p95_total_ms=percentile(total, 95),
        p50_backend_ms=percentile(backend, 50),
        p95_backend_ms=percentile(backend, 95),
        mean_input_tokens=_mean(inp),
        mean_cached_tokens=_mean(cached),
        tokens_per_observation=_mean([a + b for a, b in zip(inp, cached, strict=True)]),
        mean_top_probability=_mean(tops),
        record_path=record_path,
    )
