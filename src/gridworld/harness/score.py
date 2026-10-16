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
- ``mean_options_offered``: mean number of actions the request offered (6
  unless legal-only, story 4.5).
- System Two (story 5.4): ``plans`` and ``plans_truncated``;
  ``plan_tokens_per_plan`` (completion tokens); ``planning_s`` (summed
  ``think_ms``) and ``planning_share`` (of summed ``total_ms``, which includes
  planning, so ``decisions_per_s`` pays for thinking); ``tokens_per_episode``
  (decision prompt tokens, cached included, plus plan prompt and completion
  tokens); the per-tick ``pause_to_plan`` P(yes) as mean, p50, p90 and a
  ten-bin histogram.
"""

from __future__ import annotations

from statistics import fmean
from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict

from ..sim import Action, Cell, Observation

__all__ = [
    "EpisodeSummary",
    "RunSummary",
    "TickLog",
    "oscillation",
    "percentile",
    "summarize_episode",
    "summarize_run",
]

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
    offered: tuple[Action, ...] = tuple(Action)
    pause_p: float | None = None
    plan: Any = None  # harness.plan.PlanResult when System Two planned on this tick


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
    mean_options_offered: float | None = None
    #: System Two (story 5.4): plans made, their tokens and wall time, P(yes) of pause_to_plan.
    plan_count: int = 0
    plans_truncated: int = 0
    plan_completion_tokens: int = 0
    plan_prompt_tokens: int = 0
    think_ms: float = 0.0
    decision_tokens: int = 0
    pause_p: list[float] = []
    record_path: str | None = None
    #: Raw per-tick latencies, kept so run-level percentiles are over ticks, not episodes.
    tick_total_ms: list[float] = []
    tick_backend_ms: list[float] = []


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
    plans = [t.plan for t in ticks if t.plan is not None]
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
        mean_options_offered=_mean([float(len(t.offered)) for t in ticks]),
        plan_count=len(plans),
        plans_truncated=sum(p.truncated for p in plans),
        plan_completion_tokens=sum(p.completion_tokens for p in plans),
        plan_prompt_tokens=sum(p.prompt_tokens or 0 for p in plans),
        think_ms=sum(t.timing.get("think_ms", 0.0) for t in ticks),
        decision_tokens=sum(a + b for a, b in zip(inp, cached, strict=True)),
        pause_p=[t.pause_p for t in ticks if t.pause_p is not None],
        record_path=record_path,
        tick_total_ms=total,
        tick_backend_ms=backend,
    )


class RunSummary(BaseModel):
    """The run-level aggregate over episodes (story 4.2).

    Rates are over episodes; ``agreement`` and the latency, token and
    probability means are over all ticks; ``steps_over_oracle`` is the mean over
    episodes where it is defined; ``decisions_per_s`` is total steps over total
    ``total_ms``.
    """

    model_config = ConfigDict(frozen=True)

    episodes: int
    ticks: int
    completion: float
    died: float
    timed_out: float
    cut_short: float
    agreement: float
    steps_over_oracle: float | None
    distinct_cell_ratio: float | None
    reversals_per_episode: float | None
    decisions_per_s: float | None
    p50_total_ms: float | None
    p95_total_ms: float | None
    p50_backend_ms: float | None
    p95_backend_ms: float | None
    tokens_per_observation: float | None
    mean_cached_tokens: float | None
    mean_top_probability: float | None
    mean_options_offered: float | None = None
    plans: int = 0
    plans_per_episode: float | None = None
    plans_truncated: int = 0
    plan_tokens_per_plan: float | None = None
    planning_s: float = 0.0
    planning_share: float | None = None
    tokens_per_episode: float | None = None
    pause_p_mean: float | None = None
    pause_p_p50: float | None = None
    pause_p_p90: float | None = None
    #: Counts of per-tick P(yes) in ten bins [0, 0.1), ..., [0.9, 1.0].
    pause_p_hist: list[int] = []


def _tick_weighted(eps: list[EpisodeSummary], field: str) -> float | None:
    pairs = [(getattr(e, field), e.steps) for e in eps if getattr(e, field) is not None and e.steps]
    total = sum(n for _, n in pairs)
    return sum(v * n for v, n in pairs) / total if total else None


def summarize_run(eps: list[EpisodeSummary]) -> RunSummary:
    """Aggregate episode summaries (see :class:`RunSummary` for the weighting)."""
    n = len(eps)
    ticks = sum(e.steps for e in eps)
    rate = lambda outcome: (sum(e.outcome == outcome for e in eps) / n) if n else 0.0
    total = [ms for e in eps for ms in e.tick_total_ms]
    backend = [ms for e in eps for ms in e.tick_backend_ms]
    ratios = [e.steps_over_oracle for e in eps if e.steps_over_oracle is not None]
    plans = sum(e.plan_count for e in eps)
    plan_tokens = sum(e.plan_completion_tokens for e in eps)
    think_ms = sum(e.think_ms for e in eps)
    pause = [p for e in eps for p in e.pause_p]
    return RunSummary(
        episodes=n,
        ticks=ticks,
        completion=rate("won"),
        died=rate("died"),
        timed_out=rate("timeout"),
        cut_short=(sum(e.outcome in ("stopped", "max_ticks") for e in eps) / n) if n else 0.0,
        agreement=_tick_weighted(eps, "agreement") or 0.0,
        steps_over_oracle=_mean(ratios),
        distinct_cell_ratio=_mean([e.distinct_cell_ratio for e in eps if e.steps]),
        reversals_per_episode=_mean([float(e.reversals) for e in eps]),
        decisions_per_s=(ticks / (sum(total) / 1000)) if total and sum(total) > 0 else None,
        p50_total_ms=percentile(total, 50),
        p95_total_ms=percentile(total, 95),
        p50_backend_ms=percentile(backend, 50),
        p95_backend_ms=percentile(backend, 95),
        tokens_per_observation=_tick_weighted(eps, "tokens_per_observation"),
        mean_cached_tokens=_tick_weighted(eps, "mean_cached_tokens"),
        mean_top_probability=_tick_weighted(eps, "mean_top_probability"),
        mean_options_offered=_tick_weighted(eps, "mean_options_offered"),
        plans=plans,
        plans_per_episode=(plans / n) if n else None,
        plans_truncated=sum(e.plans_truncated for e in eps),
        plan_tokens_per_plan=(plan_tokens / plans) if plans else None,
        planning_s=think_ms / 1000,
        planning_share=(think_ms / sum(total)) if total and sum(total) > 0 else None,
        tokens_per_episode=(
            _mean(
                [
                    float(e.decision_tokens + e.plan_completion_tokens + e.plan_prompt_tokens)
                    for e in eps
                ]
            )
        ),
        pause_p_mean=_mean(pause),
        pause_p_p50=percentile(pause, 50),
        pause_p_p90=percentile(pause, 90),
        pause_p_hist=[sum(min(int(p * 10), 9) == b for p in pause) for b in range(10)]
        if pause
        else [],
    )
