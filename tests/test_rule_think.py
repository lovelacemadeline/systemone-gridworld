"""Story 5.6 — rule-based replan triggers: every N ticks, on damage, on reversals."""

from __future__ import annotations

import pytest

from gridworld import cli
from gridworld.backends.fake import FakeBackend
from gridworld.harness import run_episode
from gridworld.harness.plan import FakePlanner
from gridworld.harness.prompts import DEFAULT_PREFIX
from gridworld.harness.session import run_session
from gridworld.harness.think import SystemTwo, ThinkConfig
from gridworld.record import read_episode
from gridworld.sim import GridWorld, WorldConfig

EMPTY = WorldConfig(n_monsters=0, wall_density=0.0)


class Scripted(FakeBackend):
    """Answers a fixed action pattern by tick instead of the oracle."""

    def __init__(self, pattern):
        super().__init__()
        self.pattern = pattern

    def decide(self, request):
        resp = super().decide(request)
        from gridworld.render.text import parse_text

        tick = parse_text(request["state"]).tick
        resp["answers"]["action"]["choice"] = self.pattern[tick % len(self.pattern)]
        return resp


def rule(planner=None, **cfg):
    return SystemTwo(planner or FakePlanner(), ThinkConfig(trigger="rule", **cfg), DEFAULT_PREFIX)


def test_replan_every_10_over_30_ticks_gives_three_interval_plans():
    two = rule(replan_every=10)
    s = run_episode(GridWorld(EMPTY), Scripted(["wait"]), seed=1, max_ticks=30, hooks=two.hooks())
    assert s.steps == 30
    assert [(t, p.reason) for t, p in two.plans] == [
        (0, "interval"),
        (10, "interval"),
        (20, "interval"),
    ]


def test_replan_on_damage_plans_on_the_tick_hp_dropped(tmp_path):
    for seed in range(40):
        two, path = rule(replan_on_damage=True, cooldown=0), tmp_path / f"ep{seed}.jsonl"
        run_episode(GridWorld(), FakeBackend(), seed=seed, hooks=two.hooks(), record_path=path)
        if two.plans:
            break
    else:
        raise AssertionError("no seed had the oracle take damage")
    ticks = read_episode(path).ticks
    first = next(i for i, t in enumerate(ticks) if t.plan)
    assert ticks[first].plan["reason"] == "damage"
    assert ticks[first].observation.player_hp < ticks[first - 1].observation.player_hp
    hits = [
        i
        for i in range(1, len(ticks))
        if ticks[i].observation.player_hp < ticks[i - 1].observation.player_hp
    ]
    assert [i for i, t in enumerate(ticks) if t.plan] == hits


def test_replan_on_reversals_and_the_cooldown():
    two = rule(replan_on_reversals=2, cooldown=0)
    run_episode(
        GridWorld(EMPTY), Scripted(["west", "east"]), seed=1, max_ticks=8, hooks=two.hooks()
    )
    # moves: tick0 W, tick1 E (reversal 1 after tick1), tick2 W (reversal 2) -> plan on tick 3
    assert [t for t, _ in two.plans][:1] == [3]
    assert all(p.reason == "reversals" for _, p in two.plans)
    two = rule(replan_on_reversals=2, cooldown=100)
    run_episode(
        GridWorld(EMPTY), Scripted(["west", "east"]), seed=1, max_ticks=12, hooks=two.hooks()
    )
    assert len(two.plans) == 1


def test_coinciding_reasons_are_joined_and_the_prompt_says_why():
    planner = FakePlanner()
    two = rule(planner, replan_every=3, replan_on_reversals=2, cooldown=0)
    run_episode(
        GridWorld(EMPTY), Scripted(["west", "east"]), seed=1, max_ticks=5, hooks=two.hooks()
    )
    reasons = {t: p.reason for t, p in two.plans}
    assert reasons[0] == "interval" and reasons[3] == "interval+reversals"
    lines = planner.calls[-1]["state"].split("\n")
    ctx = next(line for line in lines if line.startswith("Recent moves:"))
    assert ctx.startswith("Recent moves: west->(") and "| hp 6 |" in ctx
    assert ctx.endswith("Planning now because: scheduled refresh, you keep moving back and forth")
    # a second plan sees the first one, so it can stop repeating itself
    assert "Plans so far this episode: 1. Your previous plan was:" in lines[-2]
    assert lines[-1].endswith("choose a different route this time.")
    assert "Plans so far" not in planner.calls[0]["state"]


def test_reasons_are_summarised_in_the_report(tmp_path):
    r = run_session(
        Scripted(["wait"]),
        episodes=2,
        out_dir=tmp_path,
        config=EMPTY,
        max_ticks=12,
        think=ThinkConfig(trigger="rule", replan_every=5),
        planner=FakePlanner(),
    )
    assert r.report.summary.plan_reasons == {"interval": 6}
    assert "| plan reasons | interval 6 |" in r.md.read_text()
    assert "rule(every 5)" in r.md.read_text() or r.report.meta.think["replan_every"] == 5


def test_rule_without_a_rule_is_refused(tmp_path, capsys):
    with pytest.raises(ValueError, match="needs"):
        ThinkConfig(trigger="rule")
    assert cli.main(["play", "--think", "rule", "--out", str(tmp_path)]) == 2
    assert "--replan-every" in capsys.readouterr().err
