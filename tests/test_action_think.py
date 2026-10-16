"""Story 5.7 — plan as a seventh option of the action question (``--think action``)."""

from __future__ import annotations

import hashlib
import json

from gridworld.backends.fake import FakeBackend
from gridworld.backends.request import PLAN_CRITERION, PLAN_OPTION
from gridworld.harness import run_episode
from gridworld.harness.plan import FakePlanner
from gridworld.harness.prompts import DEFAULT_PREFIX, PLAN_OPTION_SENTENCE
from gridworld.harness.session import run_session
from gridworld.harness.think import SystemTwo, ThinkConfig
from gridworld.record import read_episode
from gridworld.sim import Action, GridWorld, generate_map
from gridworld.view import PLAN_BAR, render_frame


class Spy(FakeBackend):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.requests = []

    def decide(self, request):
        self.requests.append(request)
        return super().decide(request)


def action(planner=None, **cfg):
    return SystemTwo(planner or FakePlanner(), ThinkConfig(trigger="action", **cfg), DEFAULT_PREFIX)


def criteria(request):
    return list(request["questions"]["action"]["criteria"])


def test_plan_is_offered_after_wait_only_in_action_mode_and_not_while_cooling_down():
    spy = Spy(plan_p=lambda obs: 0.9 if obs.tick == 1 else 0.05)
    two = action(cooldown=3)
    run_episode(GridWorld(), spy, seed=3, max_ticks=6, hooks=two.hooks(), legal_only=True)
    first = spy.requests[0]
    assert criteria(first)[-1] == PLAN_OPTION and criteria(first)[-2] == "wait"
    assert first["questions"]["action"]["criteria"][PLAN_OPTION] == PLAN_CRITERION
    assert set(first["questions"]) == {"action"}  # no second question
    # tick 0 offered, tick 1 offered (and planned, then re-asked), ticks 2-3 cool down
    offered = [PLAN_OPTION in criteria(r) for r in spy.requests]
    assert offered == [True, True, False, False, False, True, True]
    for trigger in ("never", "start", "demand"):
        spy = Spy()
        hooks = (
            SystemTwo(FakePlanner(), ThinkConfig(trigger=trigger), DEFAULT_PREFIX).hooks()
            if trigger != "never"
            else None
        )
        run_episode(GridWorld(), spy, seed=3, max_ticks=3, hooks=hooks)
        assert not any(PLAN_OPTION in criteria(r) for r in spy.requests)


def test_choosing_plan_makes_exactly_one_plan_and_reasks_without_the_option(tmp_path):
    spy = Spy(plan_p=lambda obs: 0.9 if obs.tick == 2 else 0.05)
    planner, path = FakePlanner(), tmp_path / "ep.jsonl"
    two = action(planner, cooldown=0)
    s = run_episode(GridWorld(), spy, seed=3, max_ticks=5, hooks=two.hooks(), record_path=path)
    assert len(two.plans) == 1 and two.plans[0][0] == 2 and two.plans[0][1].reason == "action"
    assert len(planner.calls) == 1
    assert len(spy.requests) == 6  # tick 2 asked twice
    first, again = spy.requests[2], spy.requests[3]
    assert PLAN_OPTION in criteria(first) and PLAN_OPTION not in criteria(again)
    assert again["state"].endswith("plan: " + planner.text)
    assert s.steps == 5 and s.agreement == 1.0  # free: the re-asked action is the oracle's
    ticks = read_episode(path).ticks
    assert [i for i, t in enumerate(ticks) if t.plan] == [2]
    assert ticks[2].plan_p == 0.9 and ticks[0].plan_p == 0.05
    assert all(t.plan_p is not None for t in ticks)
    assert ticks[2].action is not Action.WAIT and set(ticks[2].probabilities) == set(Action)


def test_tick_cost_spends_the_planning_turn_as_wait():
    spy = Spy(plan_p=lambda obs: 0.9 if obs.tick == 1 else 0.05)
    two, logs = action(cost="tick"), []
    run_episode(GridWorld(), spy, seed=3, max_ticks=3, hooks=two.hooks(after_tick=logs.append))
    assert len(spy.requests) == 3  # no re-ask
    assert logs[1].action is Action.WAIT and logs[1].plan is not None
    assert logs[0].action is not Action.WAIT and logs[2].action is not Action.WAIT


def test_plan_p_is_reported_like_pause_p(tmp_path):
    think = ThinkConfig(trigger="action", cooldown=0)
    r = run_session(
        FakeBackend(plan_p=0.2),
        episodes=2,
        seed=3,
        out_dir=tmp_path,
        max_ticks=4,
        think=think,
        planner=FakePlanner(),
    )
    s = r.report.summary
    assert s.plans == 0 and s.pause_p_mean is None
    assert abs(s.plan_p_mean - 0.2) < 1e-9 and s.plan_p_hist[2] == s.ticks
    assert "P(plan) mean / p50 / p90 | 0.20 / 0.20 / 0.20" in r.md.read_text()
    assert r.report.meta.think["trigger"] == "action"


def test_the_prefix_gains_the_sentence_only_in_action_mode(tmp_path):
    spy = Spy()
    run_session(
        spy,
        episodes=1,
        seed=3,
        out_dir=tmp_path,
        max_ticks=1,
        think=ThinkConfig(trigger="action"),
        planner=FakePlanner(),
    )
    assert spy.requests[0]["prefix"] == f"{DEFAULT_PREFIX}\n\n{PLAN_OPTION_SENTENCE}"


#: sha256 of every request a 6-tick session sends, computed on the commit
#: before story 5.7 (fbc6787). Other modes' prompts must stay byte-identical.
BEFORE = {
    "never": "c2f47fd59777b220584a7d80641f8f5b4e9a6e6cae804e627d06aeb3ac2576f8",
    "start": "7a47182b78fdeb85cac2104375159ee3c91dddf9e14c87db17d99cea954cd2fe",
    "demand": "6a51d90a1de983319d5ddea80dd631bda1cf4399341e1a86fecb07d06dc513c4",
    "rule": "7a47182b78fdeb85cac2104375159ee3c91dddf9e14c87db17d99cea954cd2fe",
}


def test_requests_in_other_modes_are_byte_identical_to_before(tmp_path):
    cases = {
        "never": None,
        "start": ThinkConfig(trigger="start"),
        "demand": ThinkConfig(trigger="demand"),
        "rule": ThinkConfig(trigger="rule", replan_every=3),
    }
    for name, think in cases.items():
        spy = Spy(noul=lambda o, q: 0.9 if o.tick == 2 else 0.1)
        run_session(
            spy,
            episodes=1,
            seed=3,
            out_dir=tmp_path / name,
            max_ticks=6,
            legal_only=True,
            labels="words",
            think=think,
            planner=FakePlanner() if think else None,
        )
        blob = json.dumps(spy.requests, sort_keys=True).encode()
        assert hashlib.sha256(blob).hexdigest() == BEFORE[name], name


def test_viewer_shows_a_seventh_bar_when_plan_is_offered():
    obs = generate_map(3)
    six = {a: 1 / 6 for a in Action}
    plain = render_frame(obs, probabilities=six, action=Action.EAST, scale=1)
    seven = render_frame(
        obs, probabilities={**six, PLAN_OPTION: 0.4}, action=Action.EAST, scale=1, plan_ticks=[0]
    )
    colours = lambda img: {c for _, c in img.getcolors(maxcolors=1 << 16)}
    assert PLAN_BAR in colours(seven) and PLAN_BAR not in colours(plain)
