"""Story 4.9 — the stuck rule (consecutive immediate reversals) and the skip key."""

from __future__ import annotations

import json

import pytest
from test_report import meta_for
from test_rule_think import Scripted

from gridworld import cli
from gridworld.backends.fake import FakeBackend
from gridworld.harness import Hooks, run_episode
from gridworld.harness.plan import FakePlanner
from gridworld.harness.prompts import DEFAULT_PREFIX
from gridworld.harness.report import build_report, comparison_table, to_markdown
from gridworld.harness.score import summarize_run
from gridworld.harness.session import run_session, session_lines
from gridworld.harness.think import SystemTwo, ThinkConfig
from gridworld.record import read_episode, replay
from gridworld.sim import GridWorld, WorldConfig

EMPTY = WorldConfig(n_monsters=0, wall_density=0.0)
SEED = 1  # an empty map where east/west both move from the start


class SpyView:
    """A headless stand-in for LiveView: always open, records the streak it is told."""

    def __init__(self):
        self.skip_requested = False
        self.reversal_streak = (0, 0)
        self.streaks: list[int] = []
        self.info_lines: list[str] = []
        self.flashes: list[str] = []

    def update(self, obs, probs=None, action=None, best=None, timing=None):
        if timing is not None:
            self.streaks.append(self.reversal_streak[0])
        return True

    def flash(self, text, seconds=1.0, obs=None):
        self.flashes.append(text)
        return True


def oscillate():
    return Scripted(["east", "west"])


def test_oscillating_backend_is_stuck_at_exactly_n(tmp_path):
    path = tmp_path / "ep.jsonl"
    view = SpyView()
    s = run_episode(
        GridWorld(EMPTY), oscillate(), seed=SEED, stuck_after=4, record_path=path, view=view
    )
    # tick 0 moves away; ticks 1..4 are the four consecutive reversals
    assert (s.outcome, s.steps, s.stuck) == ("stuck", 5, True)
    assert view.streaks == [0, 1, 2, 3, 4]
    end = read_episode(path).end
    assert (end.reason, end.reward, end.stuck_after, end.consecutive_reversals) == (
        "stuck",
        -1,
        4,
        4,
    )
    assert len(list(replay(path))) == 6
    off = run_episode(GridWorld(EMPTY), oscillate(), seed=SEED, max_ticks=20)
    assert (off.outcome, off.stuck) == ("max_ticks", False)


def test_a_non_reversal_move_resets_the_count():
    view = SpyView()
    s = run_episode(
        GridWorld(EMPTY),
        Scripted(["east", "west", "east", "wait"]),
        seed=SEED,
        stuck_after=3,
        max_ticks=12,
        view=view,
    )
    assert s.outcome == "max_ticks" and view.streaks[:6] == [0, 1, 2, 0, 0, 1]


def test_a_plan_resets_the_count():
    two = SystemTwo(
        FakePlanner(), ThinkConfig(trigger="rule", replan_every=3, cooldown=0), DEFAULT_PREFIX
    )
    view = SpyView()
    s = run_episode(
        GridWorld(EMPTY),
        oscillate(),
        seed=SEED,
        stuck_after=3,
        max_ticks=12,
        hooks=two.hooks(),
        view=view,
    )
    assert [t for t, _ in two.plans] == [0, 3, 6, 9]
    assert s.outcome == "max_ticks" and view.streaks == [0, 1, 2] * 4
    # without the replans the same moves are stuck on the fourth tick
    assert run_episode(GridWorld(EMPTY), oscillate(), seed=SEED, stuck_after=3).steps == 4


def test_skip_flag_ends_the_episode_with_reward_zero(tmp_path):
    view, path = SpyView(), tmp_path / "ep.jsonl"
    view.skip_requested = True  # stale from a previous episode: cleared at start

    def skip_on_tick_2(log):
        if log.observation.tick == 2:
            view.skip_requested = True

    s = run_episode(
        GridWorld(),
        FakeBackend(),
        seed=3,
        view=view,
        hooks=Hooks(after_tick=skip_on_tick_2),
        record_path=path,
    )
    assert (s.outcome, s.steps, view.skip_requested) == ("skipped", 3, False)
    end = read_episode(path).end
    assert (end.reason, end.reward, end.stuck_after) == ("skipped", 0, None)


def test_skipped_episodes_are_listed_but_excluded(tmp_path):
    view = SpyView()

    def skip_seed_1(log):
        if log.observation.seed == 1 and log.observation.tick == 1:
            view.skip_requested = True

    result = run_session(
        FakeBackend(),
        episodes=3,
        seed=0,
        out_dir=tmp_path,
        view=view,
        hooks=Hooks(after_tick=skip_seed_1),
        flash_s=0,
        stuck_after=5,
    )
    s = result.report.summary
    assert (s.episodes, s.skipped, s.completion, s.stuck, s.steps_over_oracle) == (
        3,
        1,
        1.0,
        0.0,
        1.0,
    )
    assert view.flashes == ["seed 0: WON", "seed 1: SKIPPED", "seed 2: WON"]
    assert view.info_lines[1] == "episodes 3   win 100%   skipped 1"
    assert result.report.meta.stuck_after == 5
    md = result.md.read_text()
    assert "| skipped | 1 |" in md and "| 1 | skipped |" in md and "- stuck after: 5" in md
    assert json.loads(result.json.read_text())["summary"]["skipped"] == 1


def test_report_has_a_stuck_column_and_counts_stuck_as_not_completed():
    backend = FakeBackend()
    won = run_episode(GridWorld(EMPTY), backend, seed=SEED)
    stuck = run_episode(GridWorld(EMPTY), oscillate(), seed=SEED, stuck_after=2)
    skipped = won.model_copy(update={"outcome": "skipped", "steps_over_oracle": None})
    s = summarize_run([won, stuck, skipped])
    assert (s.completion, s.stuck, s.died, s.timed_out, s.skipped) == (0.5, 0.5, 0.0, 0.0, 1)
    report = build_report(meta_for(backend), [won, stuck, skipped])
    md = to_markdown(report)
    assert "| timed out | 0.0% |\n| stuck | 50.0% |" in md and "| 1 | stuck |" in md
    assert "| completion | died | stuck |" in comparison_table([report])
    assert session_lines([skipped])[1] == "episodes 1   win -   skipped 1"


def test_cli_stuck_after_reaches_the_report(tmp_path, capsys):
    out = tmp_path / "runs"
    argv = ["play", "--episodes", "1", "--out", str(out)]
    assert cli.main([*argv, "--stuck-after", "-1"]) == 2
    assert cli.main([*argv, "--stuck-after", "3"]) == 0
    (js,) = out.glob("*.json")
    data = json.loads(js.read_text())
    assert data["meta"]["stuck_after"] == 3 and "stuck" in data["summary"]
    assert "| stuck | 0.0% |" in capsys.readouterr().out


def test_live_view_n_key_and_streak_text(monkeypatch):
    pygame = pytest.importorskip("pygame")
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    from gridworld.view import LiveView

    with LiveView(scale=1) as view:
        view.info_lines = session_lines([])
        view.reversal_streak = (2, 4)
        assert "reversals/ep -   in a row 2/4" in view._info()
        view.reversal_streak = (1, 0)
        assert "reversals/ep -   in a row 1" in view._info()
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_n))
        assert view._pump() and view.skip_requested
