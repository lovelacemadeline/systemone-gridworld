"""Story 5.2 — triggers never/start/demand, threshold, cooldown and think cost."""

from __future__ import annotations

from gridworld.backends.fake import FakeBackend
from gridworld.harness import run_episode
from gridworld.harness.plan import FakePlanner
from gridworld.harness.prompts import DEFAULT_PREFIX
from gridworld.harness.think import PAUSE_QUESTION, SystemTwo, ThinkConfig
from gridworld.record import read_episode
from gridworld.sim import Action, GridWorld, adjacent


class Spy(FakeBackend):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.requests = []

    def decide(self, request):
        self.requests.append(request)
        return super().decide(request)


def demand(planner=None, **cfg):
    return SystemTwo(planner or FakePlanner(), ThinkConfig(trigger="demand", **cfg), DEFAULT_PREFIX)


def test_demand_yes_once_gives_exactly_one_plan_on_that_tick(tmp_path):
    spy = Spy(noul=lambda obs, q: 0.9 if obs.tick == 2 else 0.1)
    two, path = demand(), tmp_path / "ep.jsonl"
    run_episode(GridWorld(), spy, seed=3, hooks=two.hooks(), record_path=path)
    ticks = read_episode(path).ticks
    assert [i for i, t in enumerate(ticks) if t.plan] == [2]
    assert all(t.pause_p is not None for t in ticks)
    assert ticks[2].pause_p == 0.9 and ticks[0].pause_p == 0.1
    assert len(two.plans) == 1


def test_demand_requests_carry_the_noul_and_free_cost_redecides():
    spy = Spy(noul=lambda obs, q: 0.9 if obs.tick == 1 else 0.0)
    two = demand()
    s = run_episode(GridWorld(), spy, seed=3, max_ticks=3, hooks=two.hooks())
    assert s.steps == 3 and len(spy.requests) == 4  # tick 1 asked twice
    first, again = spy.requests[1], spy.requests[2]
    assert set(first["questions"]) == {"action", PAUSE_QUESTION}
    assert first["questions"][PAUSE_QUESTION]["type"] == "noul"
    assert set(again["questions"]) == {"action"} and again["state"].endswith(
        "plan: " + FakePlanner().text
    )
    assert s.agreement == 1.0  # free: the action after planning is still the oracle's


def test_threshold_and_cooldown():
    two = demand(threshold=0.8, cooldown=3)
    run_episode(GridWorld(), FakeBackend(noul=0.85), seed=3, max_ticks=10, hooks=two.hooks())
    assert [t for t, _ in two.plans] == [0, 3, 6, 9]
    two = demand(threshold=0.9)
    run_episode(GridWorld(), FakeBackend(noul=0.85), seed=3, max_ticks=10, hooks=two.hooks())
    assert two.plans == []


def test_tick_cost_with_a_monster_adjacent_spends_the_turn_as_wait(tmp_path):
    def one_adjacent(obs, q):
        return 0.95 if sum(adjacent(m.pos, obs.player) for m in obs.monsters) == 1 else 0.0

    for seed in range(50):
        two = demand(cost="tick", cooldown=1000)
        path = tmp_path / f"ep{seed}.jsonl"
        run_episode(
            GridWorld(),
            FakeBackend(noul=one_adjacent),
            seed=seed,
            hooks=two.hooks(),
            record_path=path,
        )
        if two.plans:
            break
    else:
        raise AssertionError("no seed put exactly one monster next to the player")
    ep = read_episode(path)
    (tick,) = [t for t in ep.ticks if t.plan]
    nxt = (
        ep.ticks[ep.ticks.index(tick) + 1].observation
        if tick is not ep.ticks[-1]
        else ep.end.observation
    )
    assert tick.action is Action.WAIT
    assert nxt.player_hp == tick.observation.player_hp - 1


def test_start_with_tick_cost_waits_on_tick_zero():
    two = SystemTwo(FakePlanner(), ThinkConfig(trigger="start", cost="tick"), DEFAULT_PREFIX)
    logs = []
    run_episode(
        GridWorld(), FakeBackend(), seed=3, max_ticks=3, hooks=two.hooks(after_tick=logs.append)
    )
    assert logs[0].action is Action.WAIT and logs[1].action is not Action.WAIT
