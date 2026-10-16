"""Story 5.8 — plans are consumed as the route is walked."""

from __future__ import annotations

import pytest

from gridworld import cli
from gridworld.backends.fake import FakeBackend
from gridworld.backends.request import PLAN_OPTION
from gridworld.harness import run_episode
from gridworld.harness.plan import FakePlanner
from gridworld.harness.prompts import DEFAULT_PREFIX
from gridworld.harness.route import (
    RouteTracker,
    parse_route,
    plan_for_tail,
    strip_action_line,
)
from gridworld.harness.think import SystemTwo, ThinkConfig
from gridworld.record import read_episode
from gridworld.render.text import parse_text
from gridworld.sim import Action, GridWorld, WorldConfig, generate_map
from gridworld.view import render_frame

E, N, S, W, WAIT = Action.EAST, Action.NORTH, Action.SOUTH, Action.WEST, Action.WAIT
EMPTY = WorldConfig(n_monsters=0, wall_density=0.0)


class Scripted(FakeBackend):
    """Answers a per-tick action script (then the oracle), keeping the fake's ``plan`` pick."""

    def __init__(self, script, **kw):
        super().__init__(**kw)
        self.script, self.requests = script, []

    def decide(self, request):
        self.requests.append(request)
        resp = super().decide(request)
        tick = parse_text(request["state"]).tick
        answer = resp["answers"]["action"]
        if answer["choice"] != PLAN_OPTION:
            if callable(self.script):
                answer["choice"] = self.script(tick)
            elif tick < len(self.script):
                answer["choice"] = self.script[tick]
        return resp


def tails(spy):
    """``{tick: state}`` of each tick's last request."""
    return {parse_text(r["state"]).tick: r["state"] for r in spy.requests}


@pytest.mark.parametrize(
    "text, moves",
    [
        ("Route: north, north, east.", [N, N, E]),
        ("Route: East x4, then North", [E, E, E, E, N]),
        ("**Route:** 2 times east and 2x west; wait", [E, E, W, W, WAIT]),
        ("Goal: NW. Route: Move North repeatedly, then West. Threats: none.", [N, W]),
        ("Route: east 3, south twice, north ×2", [E, E, E, S, S, N, N]),
        ("Plan: go.\nROUTE: west -> west -> attack\nThreats: M0", [W, W, Action.ATTACK]),
        ("Route: head somewhere sensible", []),
        ("Head east toward the goal, then north.", []),  # no Route: line, no route
    ],
)
def test_parse_route_is_tolerant(text, moves):
    assert parse_route(text) == moves


def test_route_tracker_consumes_deviates_and_exhausts():
    t = RouteTracker([E, E, N])
    assert t.advance(E) == "active" and t.remaining == [E, N]
    assert t.advance(W) == "active"  # one miss is tolerated...
    assert t.advance(E) == "active" and t.misses == 0  # ...and reset by a match
    assert t.advance(N) == "exhausted" and t.remaining == []
    d = RouteTracker([E, E], deviation_limit=2)
    assert d.advance(W) == "active" and d.advance(W) == "deviated"
    assert d.advance(E) == "deviated"  # final


def test_plan_for_tail_rewrites_only_the_route_line():
    plan = "Goal: east.\nRoute: east x3.\nThreats: none."
    assert (
        plan_for_tail(plan, [E, E]) == "Goal: east.\nremaining route: east, east.\nThreats: none."
    )


def start_two(text, **cfg):
    return SystemTwo(FakePlanner(text), ThinkConfig(trigger="start", **cfg), DEFAULT_PREFIX)


def test_the_tail_carries_the_remaining_route_and_exhaustion_drops_the_plan(tmp_path):
    spy, path = Scripted([WAIT] * 10), tmp_path / "ep.jsonl"
    two = start_two("Goal: stay. Route: wait x3. Threats: none.")
    run_episode(GridWorld(EMPTY), spy, seed=1, max_ticks=5, hooks=two.hooks(), record_path=path)
    t = tails(spy)
    assert "plan: Goal: stay. remaining route: wait, wait, wait. Threats: none." in t[0]
    assert "remaining route: wait, wait." in t[1] and "remaining route: wait." in t[2]
    assert "plan:" not in t[3] and "plan:" not in t[4]
    ticks = read_episode(path).ticks
    assert [x.route_remaining for x in ticks] == [["wait"] * 3, ["wait"] * 2, ["wait"], None, None]
    assert [x.plan_dropped for x in ticks] == [None, None, None, "exhausted", None]


def test_deviation_drops_the_plan(tmp_path):
    spy, path = Scripted([WAIT] * 10), tmp_path / "ep.jsonl"
    two = start_two("Route: east x3.")
    run_episode(GridWorld(EMPTY), spy, seed=1, max_ticks=4, hooks=two.hooks(), record_path=path)
    t = tails(spy)
    assert (
        "remaining route: east, east, east." in t[0]
        and "remaining route: east, east, east." in t[1]
    )
    assert "plan:" not in t[2]
    assert [x.plan_dropped for x in read_episode(path).ticks] == [None, None, "deviated", None]


def test_deviation_limit_is_configurable():
    spy = Scripted([WAIT] * 10)
    two = start_two("Route: east x3.", route_deviation_limit=3)
    run_episode(GridWorld(EMPTY), spy, seed=1, max_ticks=4, hooks=two.hooks())
    t = tails(spy)
    assert "plan:" in t[2] and "plan:" not in t[3]


def test_exhaustion_ends_the_cooldown_and_plan_is_offered_again():
    def offered(persist):
        spy = Scripted([WAIT] * 10, plan_p=lambda o: 0.9 if o.tick == 0 else 0.05)
        cfg = ThinkConfig(trigger="action", cooldown=10, plan_persist=persist)
        two = SystemTwo(FakePlanner("Route: wait x2."), cfg, DEFAULT_PREFIX)
        run_episode(GridWorld(EMPTY), spy, seed=1, max_ticks=4, hooks=two.hooks())
        firsts = {}
        for r in spy.requests:
            firsts.setdefault(parse_text(r["state"]).tick, r)
        return [
            PLAN_OPTION in firsts[k]["questions"]["action"]["criteria"] for k in range(4)
        ], tails(spy)

    # tick 0 plans (re-ask waits: 1), tick 1 waits (2: exhausted), tick 2 drops and re-offers
    consumed, t = offered(False)
    assert consumed == [True, False, True, True] and "plan:" not in t[2]
    persisted, t = offered(True)
    assert persisted == [True, False, False, False]
    assert all("plan: Route: wait x2." in t[k] for k in range(4))  # whole plan, until replaced


def test_plan_persist_keeps_the_plan_and_the_original_route(tmp_path):
    spy, path = Scripted([WAIT] * 10), tmp_path / "ep.jsonl"
    two = start_two("Route: wait x2.", plan_persist=True)
    run_episode(GridWorld(EMPTY), spy, seed=1, max_ticks=4, hooks=two.hooks(), record_path=path)
    assert all(s.endswith("plan: Route: wait x2.") for s in tails(spy).values())
    ticks = read_episode(path).ticks
    assert all(x.plan_dropped is None and x.route_remaining is None for x in ticks)


def test_a_trailing_action_line_is_stripped_from_the_tail_but_kept_in_the_record(tmp_path):
    for persist in (False, True):
        spy, path = Scripted([WAIT] * 10), tmp_path / f"ep{persist}.jsonl"
        two = start_two("Goal: stay.\nRoute: wait x5.\n\nAction: wait", plan_persist=persist)
        run_episode(GridWorld(EMPTY), spy, seed=1, max_ticks=2, hooks=two.hooks(), record_path=path)
        assert all("Action:" not in s and "plan: Goal: stay." in s for s in tails(spy).values())
        assert read_episode(path).ticks[0].plan["plan"].endswith("Action: wait")
    assert strip_action_line("Go.\n**Action:** east\n") == "Go."
    assert strip_action_line("Action: east is tempting.\nRoute: west") == (
        "Action: east is tempting.\nRoute: west"
    )  # only a trailing line


def test_a_plan_without_a_route_stays_until_replaced():
    spy = Scripted([WAIT] * 10)
    run_episode(GridWorld(EMPTY), spy, seed=1, max_ticks=4, hooks=start_two("Head for G.").hooks())
    assert all(s.endswith("plan: Head for G.") for s in tails(spy).values())


#: The 26B's plan at tick 9 of the evidence episode (runs/20261016T181141Z-...-think-action-direct,
#: seed 0), verbatim, trailing Action line included.
EVIDENCE_PLAN = (
    "Plan: Head east toward the goal at (7,0). The path is relatively clear, but I must avoid "
    "the monsters at (9,7) and (5,9). I will move east to close the distance to the goal while "
    "staying far from the monsters' vision range.\n\nRoute: east, east, east, east, east, east, "
    "east.\nThreats: M0 (9,7) and M1 (5,9).\n\nAction: east"
)
#: The decider's actions on ticks 0-18 of that episode: up the west side, south round the wall
#: at (4,0), five easts along row 1 past the goal's neighbour (7,1), north to (8,0), then the
#: start of the (8,0)<->(9,0) ping-pong that ran to the tick limit with the plan in the tail.
EVIDENCE_ACTIONS = [N, N, N, N, N, E, N, N, E, S, E, E, E, E, E, N, E, W, E]


def test_regression_the_evidence_episode_drops_the_exhausted_plan_and_wins(tmp_path):
    # past the script, Scripted keeps the fake's own pick: the oracle's action
    def episode(persist):
        spy = Scripted(EVIDENCE_ACTIONS, plan_p=lambda o: 0.6 if o.tick == 9 else 0.003)
        cfg = ThinkConfig(trigger="action", plan_persist=persist)
        two = SystemTwo(FakePlanner(EVIDENCE_PLAN), cfg, DEFAULT_PREFIX)
        path = tmp_path / f"ep{persist}.jsonl"
        s = run_episode(GridWorld(), spy, seed=0, max_ticks=40, hooks=two.hooks(), record_path=path)
        return s, tails(spy), read_episode(path).ticks

    assert generate_map(0).player == (1, 7) and generate_map(0).goal == (7, 0)
    s, t, ticks = episode(False)
    assert [(i, x.plan["reason"]) for i, x in enumerate(ticks) if x.plan] == [(9, "action")]
    assert ticks[9].observation.player == (3, 0)
    assert all("Action: east" not in v for v in t.values())
    # south (a miss), five easts along row 1, north (a miss) to (8,0) beside the goal, where
    # the tail still says two more easts; the sixth east takes it to (9,0)...
    assert ticks[10].route_remaining == ["east"] * 7 and ticks[15].route_remaining == ["east"] * 2
    assert ticks[16].observation.player == (8, 0) and "remaining route: east, east." in t[16]
    assert ticks[17].observation.player == (9, 0) and "remaining route: east." in t[17]
    # ...west (a miss), the seventh east: exhausted, so the plan leaves the tail at tick 19
    assert ticks[18].route_remaining == ["east"] and ticks[19].plan_dropped == "exhausted"
    assert all("plan:" not in t[k] for k in t if k >= 19)
    assert all(x.route_remaining is None for x in ticks[19:])
    # with the plan gone, the decider (the fake's oracle from here) goes west twice onto G
    assert ticks[19].observation.player == (9, 0)
    assert s.outcome == "won" and s.steps == 21 and [x.action for x in ticks[19:]] == [W, W]
    # --plan-persist: the stale seven-east route is still in the tail when the episode ends
    _, t_p, _ = episode(True)
    assert "Route: east, east, east, east, east, east, east." in t_p[19]


def test_cli_flags_reach_the_think_config():
    args = cli.build_parser().parse_args(
        ["play", "--think", "action", "--plan-persist", "--route-deviation-limit", "3"]
    )
    kw = cli._think_kwargs(args)
    assert kw["plan_persist"] is True and kw["route_deviation_limit"] == 3
    default = cli._think_kwargs(cli.build_parser().parse_args(["play", "--think", "action"]))
    assert default["plan_persist"] is False and default["route_deviation_limit"] == 2


def test_viewer_shows_the_dropped_state():
    obs = generate_map(3)
    plan = render_frame(obs, scale=1, plan_text="remaining route: east.", plan_ticks=[0])
    dropped = render_frame(obs, scale=1, plan_text=None, plan_ticks=[0], plan_dropped="exhausted")
    from gridworld.view import DROPPED

    colours = lambda img: {c for _, c in img.getcolors(maxcolors=1 << 16)}
    assert DROPPED in colours(dropped) and DROPPED not in colours(plan)


def test_replay_shows_the_remaining_route_then_the_dropped_state(monkeypatch, tmp_path):
    pytest.importorskip("pygame")
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    from gridworld import view as view_mod

    path = tmp_path / "ep.jsonl"
    two = start_two("Route: wait x2.\nAction: wait")
    run_episode(
        GridWorld(EMPTY),
        Scripted([WAIT] * 9),
        seed=1,
        max_ticks=4,
        hooks=two.hooks(),
        record_path=path,
    )
    seen = []

    class Watch(view_mod.LiveView):
        def update(self, obs, *a, **kw):
            seen.append((obs.tick, self.plan_text, self.plan_dropped))
            return super().update(obs, *a, **kw)

    monkeypatch.setattr(view_mod, "LiveView", Watch)
    view_mod.play_file(path, fps=0, flash_s=0)
    by_tick = {tick: (text, dropped) for tick, text, dropped in seen}
    assert by_tick[0] == ("remaining route: wait, wait.", None)
    assert by_tick[1] == ("remaining route: wait.", None)
    assert by_tick[2] == (None, "exhausted") and by_tick[3] == (None, "exhausted")


def test_live_view_is_told_the_remaining_route_and_the_drop():
    class View:
        def __init__(self):
            self.shown = []

        def show_plan(self, text, dropped=None):
            self.shown.append((text, dropped))

    view = View()
    two = SystemTwo(
        FakePlanner("Route: wait x2."), ThinkConfig(trigger="start"), DEFAULT_PREFIX, view=view
    )
    run_episode(GridWorld(EMPTY), Scripted([WAIT] * 9), seed=1, max_ticks=3, hooks=two.hooks())
    assert view.shown == [
        ("remaining route: wait, wait.", None),
        ("remaining route: wait.", None),
        (None, "exhausted"),
    ]
