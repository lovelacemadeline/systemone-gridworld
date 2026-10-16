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

- ``action`` (story 5.7): no second question; the action question itself
  gains a seventh option ``plan`` (and the rules prefix one sentence about
  it). P(plan) is recorded on every tick that offered it. Choosing ``plan``
  makes a plan (reason ``action``) and then, per the cost, re-asks the action
  question without ``plan`` on the same tick or spends the turn as ``wait``.
  During the cooldown ``plan`` is not offered (and no P(plan) is recorded).

- ``rule`` (story 5.6): the harness decides, before the decision, from what
  it can see: ``replan_every`` N (ticks 0, N, 2N, ...: reason ``interval``),
  ``replan_on_damage`` (hp lower than the previous tick: ``damage``),
  ``replan_on_reversals`` K (K immediate reversals since the last plan:
  ``reversals``). Any combination; reasons that coincide are joined with
  ``+``. The cooldown applies (set ``cooldown`` 0 to plan on every hit).

Every plan records its ``reason`` (``start``, ``demand``, or the rule
reasons). The plan prompt's user turn is the rendered state plus a context
line: the last few moves with resulting cells, current hp, and why the plan is
being asked for, so a refreshed plan sees what went wrong.

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

Trigger = Literal["never", "start", "demand", "action", "rule"]
Cost = Literal["free", "tick"]

RECENT = 5
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
    replan_every: int | None = None
    replan_on_damage: bool = False
    replan_on_reversals: int | None = None

    def __post_init__(self) -> None:
        rules = (self.replan_every, self.replan_on_damage, self.replan_on_reversals)
        if self.trigger == "rule" and not any(rules):
            raise ValueError(
                "--think rule needs --replan-every, --replan-on-damage or --replan-on-reversals"
            )


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
        self.plan_p: list[float] = []
        self._tick: dict[str, Any] = {}
        self._planned_tick: int | None = None
        self._recent: list[tuple[str, tuple[int, int]]] = []
        self._cells: list[tuple[int, int]] = []
        self._last_hp: int | None = None
        self._reversals_since_plan = 0

    # -- planning -----------------------------------------------------------------

    def context_line(self, obs: Observation, reason: str) -> str:
        """The plan prompt's context: recent moves, hp, and why a plan is wanted now."""
        recent = ", ".join(f"{a}->({x},{y})" for a, (x, y) in self._recent[-RECENT:]) or "none"
        why = {
            "start": "start of the episode",
            "demand": "you asked to pause and plan",
            "action": "you chose to plan",
        }
        reasons = ", ".join(
            {
                "interval": "scheduled refresh",
                "damage": "you just lost hp",
                "reversals": "you keep moving back and forth",
            }.get(r, why.get(r, r))
            for r in reason.split("+")
        )
        return f"Recent moves: {recent} | hp {obs.player_hp} | Planning now because: {reasons}"

    def _plan(self, obs: Observation, reason: str) -> PlanResult:
        if self.view is not None and hasattr(self.view, "thinking"):
            self.view.thinking(obs)
        state = f"{to_text(obs)}\n{self.context_line(obs, reason)}"
        result = self.planner.plan(
            self.prefix, state, style=self.config.style, max_tokens=self.config.max_tokens
        )
        result = result.model_copy(update={"reason": reason})
        self._reversals_since_plan = 0
        self.plans.append((obs.tick, result))
        self._planned_tick = obs.tick
        self._tick["plan"] = result
        if result.plan and not result.truncated:
            self.plan_text = " ".join(result.plan.split())
        if self.view is not None and hasattr(self.view, "set_plan"):
            self.view.set_plan(obs.tick, self.plan_text, result.truncated)
        return result

    # -- hooks ----------------------------------------------------------------------

    def rule_reasons(self, obs: Observation, tick: int) -> list[str]:
        """Which rule triggers fire for this tick (before the cooldown)."""
        cfg, out = self.config, []
        if cfg.replan_every and tick % cfg.replan_every == 0:
            out.append("interval")
        if cfg.replan_on_damage and self._last_hp is not None and obs.player_hp < self._last_hp:
            out.append("damage")
        if cfg.replan_on_reversals and self._reversals_since_plan >= cfg.replan_on_reversals:
            out.append("reversals")
        return out

    def before_decision(self, obs: Observation, tick: int) -> str | None:
        cfg = self.config
        if cfg.trigger == "start" and tick == 0 and not self.plans:
            self._plan(obs, "start")
        elif cfg.trigger == "rule":
            reasons = self.rule_reasons(obs, tick)
            if reasons and self._cooled(tick):
                self._plan(obs, "+".join(reasons))
        self._last_hp = obs.player_hp
        return f"plan: {self.plan_text}" if self.plan_text else None

    def extra_questions(self, obs: Observation, tick: int) -> dict[str, Any] | None:
        if self.config.trigger != "demand":
            return None
        return {PAUSE_QUESTION: {"type": "noul", "instructions": PAUSE_INSTRUCTIONS}}

    def offer_plan(self, obs: Observation, tick: int) -> bool:
        """``--think action``: offer the ``plan`` option unless cooling down."""
        return self.config.trigger == "action" and self._cooled(tick)

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
                    self._plan(obs, "demand")
        elif cfg.trigger == "action":
            if decision.plan_p is not None:
                self.plan_p.append(decision.plan_p)
            if decision.chose_plan:
                self._plan(obs, "action")
        if self._planned_tick != tick:
            return None
        if cfg.cost == "tick":
            return Directive(action=Action.WAIT)
        if cfg.trigger in ("demand", "action"):
            return Directive(redecide=True)
        return None

    def observe_tick(self, log: Any) -> None:
        """Track moves, cells and reversals (the rule triggers and the plan context)."""
        if not self._cells:
            self._cells.append(log.observation.player)
        self._cells.append(log.after.player)
        self._recent.append((log.action.value, log.after.player))
        c = self._cells
        if len(c) >= 3 and c[-1] == c[-3] and c[-1] != c[-2]:
            self._reversals_since_plan += 1

    def tick_extras(self) -> dict[str, Any]:
        out, self._tick = self._tick, {}
        return out

    def hooks(self, after_tick=None) -> Hooks:
        """The loop hooks, with an optional extra ``after_tick`` passed through."""

        def _after(log: Any) -> None:
            self.observe_tick(log)
            if after_tick is not None:
                after_tick(log)

        return Hooks(
            before_decision=self.before_decision,
            extra_questions=self.extra_questions,
            after_decision=self.after_decision,
            tick_extras=self.tick_extras,
            after_tick=_after,
            offer_plan=self.offer_plan,
        )
