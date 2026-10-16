"""The episode loop (story 4.1): observe, render, ask, act, log.

One tick of :func:`run_episode`:

1. the oracle's action for the current observation (outside the timed span);
2. **render**: the memory tail (plus any hook text) and history are gathered
   and :func:`~gridworld.backends.request.build_request` renders the state;
3. **backend**: :func:`~gridworld.backends.adapter.call` validates, asks the
   backend, validates the answer;
4. **step**: the chosen action is stepped (or a hook's override);
5. the tick is recorded (observation, action, probabilities, oracle action,
   usage, timing ``{render_ms, backend_ms, think_ms, step_ms, total_ms}``, and
   System Two's ``plan`` / ``pause_p`` / ``plan_p`` when present), the memory is told what
   happened, and the live view (if any) is updated.

The episode ends when the sim ends it, when ``max_ticks`` is reached
(``max_ticks``), or when the view is closed (``stopped``).

**Hooks** (:class:`Hooks`) are the seam for System Two (Epic 5):
``before_decision(obs, tick)`` may return text that is appended to this tick's
memory tail (a plan), ``extra_questions`` adds questions (the ``pause_to_plan``
noul), ``offer_plan`` adds the ``plan`` option to the first request's
action question (story 5.7), ``after_decision`` may plan and then ask for a re-decision or override
the action (:class:`Directive`), ``tick_extras`` supplies record fields, and
``after_tick(log)`` sees every tick. :class:`~gridworld.harness.think.SystemTwo`
implements them.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..backends.adapter import Decision, call
from ..backends.base import Backend
from ..backends.request import PLAN_OPTION, Mode, build_request
from ..oracle import oracle, play_episode
from ..record import EpisodeHeader, EpisodeRecorder, git_rev
from ..sim import Action, GridWorld, Observation
from .memory import Memory, NoMemory
from .prompts import DEFAULT_PREFIX
from .score import EpisodeSummary, TickLog, summarize_episode

__all__ = ["Directive", "Hooks", "oracle_steps", "run_episode"]


@dataclass
class Directive:
    """What :attr:`Hooks.after_decision` may ask of the loop for this tick."""

    #: Step this instead of the decided action (``--think-cost tick``: ``wait``).
    action: Action | None = None
    #: Ask the backend again (without extra questions) before stepping.
    redecide: bool = False


@dataclass
class Hooks:
    """Optional per-tick callbacks (see the module docstring).

    ``extra_questions(obs, tick)`` adds questions to the first request of a
    tick; ``after_decision(obs, tick, decision)`` may return a
    :class:`Directive`; ``tick_extras()`` returns fields for this tick's record
    (``plan``, ``pause_p``). ``offer_plan(obs, tick)`` says whether the first
    request of a tick offers the ``plan`` option; the decision's P(plan) is
    recorded as ``plan_p`` and shown as a seventh bar. Time spent in ``before_decision`` and
    ``after_decision`` is the tick's ``think_ms``.
    """

    before_decision: Callable[[Observation, int], str | None] | None = None
    after_tick: Callable[[TickLog], None] | None = None
    extra_questions: Callable[[Observation, int], dict[str, Any] | None] | None = None
    after_decision: Callable[[Observation, int, Decision], Directive | None] | None = None
    tick_extras: Callable[[], dict[str, Any]] | None = None
    offer_plan: Callable[[Observation, int], bool] | None = None


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
    legal_only: bool = False,
    label_style: str | None = None,
    planner: str | None = None,
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
            planner=planner,
            git_rev=rev if rev is not None else git_rev(),
        )
        rec = EpisodeRecorder(record_path, header)
    ticks: list[TickLog] = []
    reason, reward = None, 0
    try:
        while True:
            best = oracle(obs)
            t0 = time.perf_counter()
            spent = {"render_ms": 0.0, "backend_ms": 0.0, "think_ms": 0.0}

            def ask(first: bool, obs=obs, spent=spent):
                ta = time.perf_counter()
                tail = memory.tail(obs)
                extra = None
                if hooks.before_decision:
                    tb = time.perf_counter()
                    extra = hooks.before_decision(obs, obs.tick)
                    spent["think_ms"] += _ms(tb, time.perf_counter())
                if extra:
                    tail = f"{tail} | {extra}" if tail else extra
                questions = (
                    hooks.extra_questions(obs, obs.tick)
                    if first and hooks.extra_questions
                    else None
                )
                plan_option = bool(first and hooks.offer_plan and hooks.offer_plan(obs, obs.tick))
                built = build_request(
                    obs,
                    mode=mode,
                    prefix=prefix,
                    memory_tail=tail,
                    history=memory.history(),
                    legal_only=legal_only,
                    label_style=label_style,
                    extra_questions=questions,
                    plan_option=plan_option,
                )
                tc = time.perf_counter()
                spent["render_ms"] += _ms(ta, tc)
                decision = call(backend, built.request)
                spent["backend_ms"] += _ms(tc, time.perf_counter())
                return built, decision

            built, decision = ask(True)
            plan_p = decision.plan_p
            spent["render_ms"] -= spent["think_ms"]
            directive = None
            if hooks.after_decision:
                th = time.perf_counter()
                directive = hooks.after_decision(obs, obs.tick, decision)
                spent["think_ms"] += _ms(th, time.perf_counter())
            if directive is not None and directive.redecide:
                think_before = spent["think_ms"]
                built, decision = ask(False)
                spent["render_ms"] -= spent["think_ms"] - think_before
            action = decision.action
            if directive is not None and directive.action is not None:
                action = directive.action
            t2 = time.perf_counter()
            result = world.step(action)
            t3 = time.perf_counter()
            timing = {**spent, "step_ms": _ms(t2, t3), "total_ms": _ms(t0, t3)}
            extras = hooks.tick_extras() if hooks.tick_extras else {}
            log = TickLog(
                observation=obs,
                action=action,
                oracle_action=best,
                probabilities=decision.probabilities,
                usage=decision.usage,
                timing=timing,
                after=result.observation,
                offered=built.offered,
                pause_p=extras.get("pause_p"),
                plan_p=plan_p,
                plan=extras.get("plan"),
            )
            ticks.append(log)
            if rec is not None:
                rec.tick(
                    obs,
                    action,
                    best,
                    decision.probabilities,
                    timing,
                    decision.usage,
                    built.offered,
                    pause_p=extras.get("pause_p"),
                    plan_p=plan_p,
                    plan=extras["plan"].model_dump() if extras.get("plan") else None,
                )
            memory.observe(obs, built.text, action, result.observation)
            if hooks.after_tick:
                hooks.after_tick(log)
            open_ = True
            if view is not None:
                shown: dict[Any, float] = dict(decision.probabilities)
                if plan_p is not None:
                    shown[PLAN_OPTION] = plan_p
                open_ = view.update(obs, shown, action, best, timing)
            obs = result.observation
            if result.done:
                reason, reward = result.info["reason"], result.reward
            elif not open_:
                reason = "stopped"
            elif max_ticks is not None and len(ticks) >= max_ticks:
                reason = "max_ticks"
            if reason is not None:
                if view is not None and open_:
                    view.update(obs)  # the terminal state, for the end-of-episode flash
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
