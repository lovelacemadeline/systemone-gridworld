"""Story 5.3 — viewer plan panel, thinking state and planning-tick markers."""

from __future__ import annotations

import pytest

from gridworld.backends.fake import FakeBackend
from gridworld.harness import run_episode
from gridworld.harness.plan import FakePlanner
from gridworld.harness.prompts import DEFAULT_PREFIX
from gridworld.harness.think import SystemTwo, ThinkConfig
from gridworld.record import read_episode
from gridworld.sim import GridWorld, generate_map
from gridworld.view import STRIP_PLAN, THINKING, TRUNCATED, render_frame


def colours(img):
    return {c for _, c in img.getcolors(maxcolors=1 << 16)}


def test_plan_panel_draws_only_with_system_two():
    obs = generate_map(3).model_copy(update={"tick": 5})
    plain = render_frame(obs, scale=1)
    panel = render_frame(obs, scale=1, plan_text="Go west then north.", plan_ticks=[2])
    assert panel.height > plain.height
    assert STRIP_PLAN in colours(panel) and STRIP_PLAN not in colours(plain)


def test_truncated_badge_and_thinking_state():
    obs = generate_map(3)
    done = render_frame(obs, scale=1, plan_text="x", plan_ticks=[0])
    cut = render_frame(obs, scale=1, plan_truncated=True, plan_ticks=[0])
    thinking = render_frame(obs, scale=1, thinking=True, plan_ticks=[])
    assert TRUNCATED in colours(cut) and TRUNCATED not in colours(done)
    assert THINKING in colours(thinking) and THINKING not in colours(done)


def test_replay_plan_text_changes_on_recorded_ticks(monkeypatch, tmp_path):
    pytest.importorskip("pygame")
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    from gridworld import view as view_mod

    texts = iter(["Plan one.", "Plan two."])

    class Two(FakePlanner):
        def plan(self, *a, **kw):
            self.text = next(texts)
            return super().plan(*a, **kw)

    path = tmp_path / "ep.jsonl"
    two = SystemTwo(Two(), ThinkConfig(trigger="demand", cooldown=1), DEFAULT_PREFIX)
    noul = lambda obs, q: 0.9 if obs.tick in (1, 4) else 0.0
    run_episode(
        GridWorld(),
        FakeBackend(noul=noul),
        seed=3,
        max_ticks=6,
        hooks=two.hooks(),
        record_path=path,
    )
    seen = []

    class Watch(view_mod.LiveView):
        def update(self, obs, *a, **kw):
            seen.append((obs.tick, self.plan_text, list(self.plan_ticks or [])))
            return super().update(obs, *a, **kw)

    monkeypatch.setattr(view_mod, "LiveView", Watch)
    view_mod.play_file(path, fps=0)
    by_tick = {t: (text, marks) for t, text, marks in seen}
    assert by_tick[0][0] is None and by_tick[1][0] == "Plan one." and by_tick[3][0] == "Plan one."
    assert by_tick[4][0] == "Plan two." and by_tick[5][1] == [1, 4]
    assert read_episode(path).ticks[4].plan["plan"] == "Plan two."


def test_live_view_shows_thinking_before_the_plan_call(monkeypatch, tmp_path):
    pytest.importorskip("pygame")
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    from gridworld.view import LiveView

    events = []

    class Planner(FakePlanner):
        def plan(self, *a, **kw):
            events.append("plan")
            return super().plan(*a, **kw)

    with LiveView(scale=1) as view:
        orig = view.thinking
        view.thinking = lambda obs: (events.append("thinking"), orig(obs))[1]
        two = SystemTwo(Planner("Go."), ThinkConfig(trigger="start"), DEFAULT_PREFIX, view=view)
        run_episode(GridWorld(), FakeBackend(), seed=3, max_ticks=2, hooks=two.hooks(), view=view)
        assert events == ["thinking", "plan"]
        assert view.plan_text == "Go." and view.plan_ticks == [0]
