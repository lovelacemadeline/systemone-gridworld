"""The episode loop (story 4.1): observe, render, ask, act, log.

One tick of :func:`run_episode`:

1. the oracle's action for the current observation (outside the timed span);
2. **render**: the memory tail (plus any hook text) and history are gathered
   and :func:`~gridworld.backends.request.build_request` renders the state;
3. **backend**: :func:`~gridworld.backends.adapter.call` validates, asks the
   backend, validates the answer;
4. **step**: the chosen action is stepped;
5. the tick is recorded (observation, action, probabilities, oracle action,
   usage, timing ``{render_ms, backend_ms, step_ms, total_ms}``), the memory is
   told what happened, and the live view (if any) is updated.

The episode ends when the sim ends it, when ``max_ticks`` is reached
(``max_ticks``), or when the view is closed (``stopped``).

**Hooks** (:class:`Hooks`) are the seam for System Two (Epic 5):
``before_decision(obs, tick)`` may return text that is appended to this tick's
memory tail (a plan, say), and ``after_tick(log)`` sees every tick.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..backends.adapter import call
from ..backends.base import Backend
from ..backends.request import Mode, build_request
from ..oracle import oracle, play_episode
from ..record import EpisodeHeader, EpisodeRecorder, git_rev
from ..sim import GridWorld, Observation
from .memory import Memory, NoMemory
from .prompts import DEFAULT_PREFIX
from .score import EpisodeSummary, TickLog, summarize_episode

__all__ = ["Hooks", "oracle_steps", "run_episode"]


@dataclass
class Hooks:
    """Optional per-tick callbacks (see the module docstring)."""

    before_decision: Callable[[Observation, int], str | None] | None = None
    after_tick: Callable[[TickLog], None] | None = None


def _ms(a: float, b: float) -> float:
    return (b - a) * 1000


def oracle_steps(world: GridWorld, seed: int) -> int | None:
    """Ticks the oracle takes to win ``seed`` on ``world``'s config (``None`` if it fails)."""
    actions, last = play_episode(GridWorld(world.config), seed)
    return len(actions) if last.info["reason"] == "goal" else None


def run_episode(
    world: GridWorld,
    backend: Backend,
    *,
    seed: int,
    mode: Mode = "text",
    prefix: str = DEFAULT_PREFIX,
    memory: Memory | None = None,
    record_path: str | Path | None = None,
    view: Any = None,
    hooks: Hooks | None = None,
    max_ticks: int | None = None,
    rev: str | None = None,
) -> EpisodeSummary:
    """Play one episode of ``seed`` with ``backend``; record it and return its summary."""
    memory = memory or NoMemory()
    hooks = hooks or Hooks()
    obs = world.reset(seed)
    memory.reset()
    rec = None
    if record_path is not None:
        header = EpisodeHeader(
            seed=seed,
            config=world.config,
            backend=backend.id,
            mode=mode,
            memory=memory.name,
            git_rev=rev if rev is not None else git_rev(),
        )
        rec = EpisodeRecorder(record_path, header)
    ticks: list[TickLog] = []
    reason, reward = None, 0
    try:
        while True:
            best = oracle(obs)
            t0 = time.perf_counter()
            tail = memory.tail(obs)
            extra = hooks.before_decision(obs, obs.tick) if hooks.before_decision else None
            if extra:
                tail = f"{tail} | {extra}" if tail else extra
            built = build_request(
                obs, mode=mode, prefix=prefix, memory_tail=tail, history=memory.history()
            )
            t1 = time.perf_counter()
            decision = call(backend, built.request)
            t2 = time.perf_counter()
            result = world.step(decision.action)
            t3 = time.perf_counter()
            timing = {
                "render_ms": _ms(t0, t1),
                "backend_ms": _ms(t1, t2),
                "step_ms": _ms(t2, t3),
                "total_ms": _ms(t0, t3),
            }
            log = TickLog(
                observation=obs,
                action=decision.action,
                oracle_action=best,
                probabilities=decision.probabilities,
                usage=decision.usage,
                timing=timing,
                after=result.observation,
            )
            ticks.append(log)
            if rec is not None:
                rec.tick(obs, decision.action, best, decision.probabilities, timing, decision.usage)
            memory.observe(obs, built.text, decision.action, result.observation)
            if hooks.after_tick:
                hooks.after_tick(log)
            open_ = True
            if view is not None:
                open_ = view.update(obs, decision.probabilities, decision.action, best, timing)
            obs = result.observation
            if result.done:
                reason, reward = result.info["reason"], result.reward
            elif not open_:
                reason = "stopped"
            elif max_ticks is not None and len(ticks) >= max_ticks:
                reason = "max_ticks"
            if reason is not None:
                break
    except KeyboardInterrupt:
        reason = "stopped"
        raise
    finally:
        if rec is not None:
            if reason is not None:
                rec.end(obs, reward, reason)
            rec.close()
    return summarize_episode(
        seed,
        ticks,
        reason,
        oracle_steps(world, seed),
        str(record_path) if record_path is not None else None,
    )
