"""System Two controller (stories 5.1, 5.2): when to plan, and what a plan changes.

:class:`SystemTwo` plugs into the episode loop through :class:`~gridworld.harness.loop.Hooks`.
It holds the current plan for the episode; the plan's text (only the plan,
never the trace) is appended to every decision's memory tail as
``plan: <text>`` until a new plan replaces it. A truncated plan or an empty
one never replaces the current plan; it is recorded and shown as truncated.

Triggers (``--think``):

- ``never``: no SystemTwo at all (the baseline);
- ``start``: one plan before the first decision of each episode;
- ``demand``: every tick's first request also asks the ``noul`` question
  ``pause_to_plan`` ("Should you pause to make a plan before acting?"). Its
  P(yes) is recorded every tick; when it is at least ``threshold`` and at least
  ``cooldown`` ticks have passed since the last plan, a plan is made.

Cost (``--think-cost``): ``free`` (default) plans before the action on the
same tick — the decision is asked again with the new plan in the tail, and
monsters get no extra turn; ``tick`` spends the turn: the tick's action is
``wait`` (adjacent monsters hit) and the plan steers from the next tick. With
``start``, the cost applies to tick 0.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from ..backends.adapter import Decision
from ..render.text import to_text
from ..sim import Action, Observation
from .loop import Directive, Hooks
from .plan import DEFAULT_PLAN_MAX_TOKENS, Planner, PlanResult, PlanStyle

__all__ = ["PAUSE_INSTRUCTIONS", "PAUSE_QUESTION", "Cost", "SystemTwo", "ThinkConfig", "Trigger"]

Trigger = Literal["never", "start", "demand"]
Cost = Literal["free", "tick"]

PAUSE_QUESTION = "pause_to_plan"
PAUSE_INSTRUCTIONS = "Should you pause to make a plan before acting?"


@dataclass(frozen=True)
class ThinkConfig:
    trigger: Trigger = "never"
    style: PlanStyle = "direct"
    max_tokens: int = DEFAULT_PLAN_MAX_TOKENS
    threshold: float = 0.7
    cooldown: int = 5
    cost: Cost = "free"


class SystemTwo:
    """Plans for one episode at a time; call :meth:`reset` (or make a new one) per episode."""

    def __init__(
        self, planner: Planner, config: ThinkConfig, prefix: str, view: Any = None
    ) -> None:
        self.planner, self.config, self.prefix, self.view = planner, config, prefix, view
        self.reset()

    def reset(self) -> None:
        self.plan_text: str | None = None
        self.plans: list[tuple[int, PlanResult]] = []
        self.pause_p: list[float] = []
        self._tick: dict[str, Any] = {}
        self._planned_tick: int | None = None

    # -- planning -----------------------------------------------------------------

    def _plan(self, obs: Observation) -> PlanResult:
        if self.view is not None and hasattr(self.view, "thinking"):
            self.view.thinking(obs)
        result = self.planner.plan(
            self.prefix, to_text(obs), style=self.config.style, max_tokens=self.config.max_tokens
        )
        self.plans.append((obs.tick, result))
        self._planned_tick = obs.tick
        self._tick["plan"] = result
        if result.plan and not result.truncated:
            self.plan_text = " ".join(result.plan.split())
        if self.view is not None and hasattr(self.view, "set_plan"):
            self.view.set_plan(obs.tick, self.plan_text, result.truncated)
        return result

    # -- hooks ----------------------------------------------------------------------

    def before_decision(self, obs: Observation, tick: int) -> str | None:
        if self.config.trigger == "start" and tick == 0 and not self.plans:
            self._plan(obs)
        return f"plan: {self.plan_text}" if self.plan_text else None

    def extra_questions(self, obs: Observation, tick: int) -> dict[str, Any] | None:
        if self.config.trigger != "demand":
            return None
        return {PAUSE_QUESTION: {"type": "noul", "instructions": PAUSE_INSTRUCTIONS}}

    def _cooled(self, tick: int) -> bool:
        last = self.plans[-1][0] if self.plans else None
        return last is None or tick - last >= self.config.cooldown

    def after_decision(self, obs: Observation, tick: int, decision: Decision) -> Directive | None:
        cfg = self.config
        if cfg.trigger == "demand":
            answer = decision.response["answers"].get(PAUSE_QUESTION) or {}
            p = answer.get("noul")
            if p is not None:
                self.pause_p.append(float(p))
                self._tick["pause_p"] = float(p)
                if p >= cfg.threshold and self._cooled(tick):
                    self._plan(obs)
        if self._planned_tick != tick:
            return None
        if cfg.cost == "tick":
            return Directive(action=Action.WAIT)
        if cfg.trigger == "demand":
            return Directive(redecide=True)
        return None

    def tick_extras(self) -> dict[str, Any]:
        out, self._tick = self._tick, {}
        return out

    def hooks(self, after_tick=None) -> Hooks:
        """The loop hooks, with an optional extra ``after_tick`` passed through."""
        return Hooks(
            before_decision=self.before_decision,
            extra_questions=self.extra_questions,
            after_decision=self.after_decision,
            tick_extras=self.tick_extras,
            after_tick=after_tick,
        )
