"""System Two controller (stories 5.1, 5.2): when to plan, and what a plan changes.

:class:`SystemTwo` plugs into the episode loop through :class:`~gridworld.harness.loop.Hooks`.
It holds the current plan for the episode; the plan's text (only the plan,
never the trace) is appended to every decision's memory tail as
``plan: <text>`` until a new plan replaces it. A truncated plan or an empty
one never replaces the current plan; it is recorded and shown as truncated.

Triggers (``--think``): ``never`` (no SystemTwo at all, the baseline) and
``start`` (one plan before the first decision of each episode).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from ..backends.adapter import Decision
from ..render.text import to_text
from ..sim import Observation
from .loop import Directive, Hooks
from .plan import DEFAULT_PLAN_MAX_TOKENS, Planner, PlanResult, PlanStyle

__all__ = ["SystemTwo", "ThinkConfig", "Trigger"]

Trigger = Literal["never", "start"]


@dataclass(frozen=True)
class ThinkConfig:
    trigger: Trigger = "never"
    style: PlanStyle = "direct"
    max_tokens: int = DEFAULT_PLAN_MAX_TOKENS


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
        self._tick: dict[str, Any] = {}

    # -- planning -----------------------------------------------------------------

    def _plan(self, obs: Observation) -> PlanResult:
        if self.view is not None and hasattr(self.view, "thinking"):
            self.view.thinking(obs)
        result = self.planner.plan(
            self.prefix, to_text(obs), style=self.config.style, max_tokens=self.config.max_tokens
        )
        self.plans.append((obs.tick, result))
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

    def after_decision(self, obs: Observation, tick: int, decision: Decision) -> Directive | None:
        return None

    def tick_extras(self) -> dict[str, Any]:
        out, self._tick = self._tick, {}
        return out

    def hooks(self, after_tick=None) -> Hooks:
        """The loop hooks, with an optional extra ``after_tick`` passed through."""
        return Hooks(
            before_decision=self.before_decision,
            after_decision=self.after_decision,
            tick_extras=self.tick_extras,
            after_tick=after_tick,
        )
