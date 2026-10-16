"""Story 1.5 — the final frame before the result flash, and the rolling decision rate."""

from __future__ import annotations

import pytest

from gridworld.backends.fake import FakeBackend
from gridworld.harness import run_episode
from gridworld.harness.plan import FakePlanner
from gridworld.harness.prompts import DEFAULT_PREFIX
from gridworld.harness.session import run_session
from gridworld.harness.think import SystemTwo, ThinkConfig
from gridworld.record import read_episode
from gridworld.sim import GridWorld, generate_map
from gridworld.view import DecisionRate, render_frame


@pytest.fixture
def watched(monkeypatch):
    """A headless LiveView subclass that logs update / hold_frame / flash in order."""
    pytest.importorskip("pygame")
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    from gridworld import view as view_mod

    events = []

    class Watch(view_mod.LiveView):
        def update(self, obs, probabilities=None, *a, **kw):
            events.append(("update", obs, probabilities))
            return super().update(obs, probabilities, *a, **kw)

        def hold_frame(self):
            events.append(("hold",))
            return super().hold_frame()

        def flash(self, text, *a, **kw):
            events.append(("flash", text))
            return super().flash(text, *a, **kw)

    monkeypatch.setattr(view_mod, "LiveView", Watch)
    return Watch, events


def assert_final_frame_then_flash(events, end_obs):
    i = next(i for i, e in enumerate(events) if e[0] == "flash")
    kind, obs, probs = events[i - 2]
    assert kind == "update" and obs == end_obs and probs  # the end state, with the last bars
    assert events[i - 1] == ("hold",)
    assert end_obs.player == end_obs.goal  # the move onto G is on screen


def test_live_play_draws_the_end_observation_before_the_flash(watched, tmp_path):
    Watch, events = watched
    with Watch(scale=1) as view:
        r = run_session(FakeBackend(), episodes=1, seed=3, out_dir=tmp_path, view=view, flash_s=0)
    (path,) = r.episode_dir.glob("seed-*.jsonl")
    end = read_episode(path).end
    assert end.reason == "goal"
    assert_final_frame_then_flash(events, end.observation)
    assert events[-1] == ("flash", "seed 3: WON")


def test_replay_draws_the_end_observation_before_the_flash(watched, tmp_path):
    from gridworld import view as view_mod

    _, events = watched
    path = tmp_path / "ep.jsonl"
    run_episode(GridWorld(), FakeBackend(), seed=3, record_path=path)
    episode = read_episode(path)
    shown = view_mod.play_file(path, fps=0, flash_s=0)
    assert shown == len(episode.ticks) + 1
    assert_final_frame_then_flash(events, episode.end.observation)
    assert events[-1] == ("flash", "seed 3: WON")


def test_rolling_rate_ignores_planning_and_old_ticks():
    rate = DecisionRate()
    for _ in range(3):  # a slow first prefill and two plans
        rate.add({"think_ms": 900.0, "total_ms": 1000.0})
    assert rate.recent_per_second == pytest.approx(10.0)  # 3 decisions in 300 ms
    for _ in range(10):
        rate.add({"think_ms": 0.0, "total_ms": 50.0})
    assert rate.recent_per_second == pytest.approx(20.0)  # only the last 10 ticks
    assert rate.per_second == pytest.approx(13 / 3.5)  # the session figure is unchanged
    assert DecisionRate().recent_per_second is None


def test_rolling_rate_with_the_fake_backends_fixed_latency():
    class View:
        def __init__(self):
            self.rate = DecisionRate()

        def update(self, obs, probabilities=None, action=None, oracle=None, timing=None):
            self.rate.add(timing)
            return True

    view = View()
    two = SystemTwo(
        FakePlanner(latency_s=0.1),
        ThinkConfig(trigger="rule", replan_every=4, cooldown=0),
        DEFAULT_PREFIX,
    )
    run_episode(
        GridWorld(),
        FakeBackend(latency_s=0.02),
        seed=3,
        max_ticks=10,
        hooks=two.hooks(),
        view=view,
    )
    now, session = view.rate.recent_per_second, view.rate.per_second
    assert 25 < now <= 50  # one 20 ms call per tick, plans excluded
    assert session < 0.6 * now  # three 100 ms plans dilute the session figure


def test_the_panel_shows_now_beside_the_session_rate():
    obs = generate_map(3)
    plain = render_frame(obs, decisions_per_s=1.2, scale=1)
    both = render_frame(obs, decisions_per_s=1.2, recent_per_s=3.0, scale=1)
    assert plain.tobytes() != both.tobytes()
