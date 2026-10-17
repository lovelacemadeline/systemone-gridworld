"""Stories 4.9 / 4.10 — the stuck rule (ticks without a new cell) and the skip key."""

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
        self.stuck_streak = (0, 0)
        self.streaks: list[int] = []
        self.info_lines: list[str] = []
        self.flashes: list[str] = []

    def update(self, obs, probs=None, action=None, best=None, timing=None):
        if timing is not None:
            self.streaks.append(self.stuck_streak[0])
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
    # tick 0 moves onto a new cell; ticks 1..4 only revisit the two known cells
    assert (s.outcome, s.steps, s.stuck) == ("stuck", 5, True)
    assert view.streaks == [0, 1, 2, 3, 4]
    end = read_episode(path).end
    assert (end.reason, end.reward, end.stuck_after, end.ticks_without_new_cell) == (
        "stuck",
        -1,
        4,
        4,
    )
    assert len(list(replay(path))) == 6
    off = run_episode(GridWorld(EMPTY), oscillate(), seed=SEED, max_ticks=20)
    assert (off.outcome, off.stuck) == ("max_ticks", False)


def test_only_a_new_cell_resets_the_count():
    # west, east, west, west from (7, 0): the second west of each cycle reaches a new cell
    view = SpyView()
    s = run_episode(
        GridWorld(EMPTY),
        Scripted(["west", "east", "west", "west"]),
        seed=SEED,
        stuck_after=3,
        max_ticks=8,
        view=view,
    )
    assert s.outcome == "max_ticks" and view.streaks == [0, 1, 2, 0, 0, 1, 2, 0]


def test_a_wait_does_not_reset_the_count():
    # story 4.9 reset on any non-reversal tick, so a wait broke the streak
    view = SpyView()
    s = run_episode(
        GridWorld(EMPTY),
        Scripted(["east", "west", "east", "wait"]),
        seed=SEED,
        stuck_after=3,
        max_ticks=12,
        view=view,
    )
    assert (s.outcome, s.steps) == ("stuck", 4) and view.streaks == [0, 1, 2, 3]


def test_a_plan_does_not_reset_the_count():
    # story 4.9 reset on every plan, so replan_every below N made the rule unreachable
    two = SystemTwo(
        FakePlanner(), ThinkConfig(trigger="rule", replan_every=3, cooldown=0), DEFAULT_PREFIX
    )
    view = SpyView()
    s = run_episode(
        GridWorld(EMPTY),
        oscillate(),
        seed=SEED,
        stuck_after=5,
        max_ticks=12,
        hooks=two.hooks(),
        view=view,
    )
    assert [t for t, _ in two.plans] == [0, 3]
    assert (s.outcome, s.steps) == ("stuck", 6) and view.streaks == [0, 1, 2, 3, 4, 5]


# Observed traces (E2B, image vt140, think on with replan_every 5, --stuck-after 10,
# 2026-10-17): both ran 200 ticks to timeout. Seed 0 paces a column of ~10 cells
# (114 reversals interleaved with waits/attacks); seed 7 parks on (0, 3) and waits.
SEED0_ACTIONS = (
    ["north"] * 5
    + ["south"] * 7
    + ["wait"] * 3
    + ["north"] * 4
    + ["south", "attack", "attack", "south", "south", "south"]
    + ["north", "south"] * 2
    + ["north", "west"]
    + ["north", "south"] * 4
    + ["north"]
)
SEED0_CELLS = [
    (1, 7),
    (1, 6),
    (1, 5),
    (1, 4),
    (1, 3),
    (1, 2),
    (1, 3),
    (1, 4),
    (1, 5),
    (1, 6),
    (1, 7),
    (1, 8),
    (1, 9),
    (1, 9),
    (1, 9),
    (1, 9),
    (1, 8),
    (1, 7),
    (1, 6),
    (1, 5),
    (1, 6),
    (1, 6),
]
SEED7_ACTIONS = ["south", "west", "south"] + ["wait"] * 37
SEED7_CELLS = [(1, 1), (1, 2), (0, 2)] + [(0, 3)] * 10


@pytest.mark.parametrize(
    ("seed", "actions", "cells", "steps"),
    [(0, SEED0_ACTIONS, SEED0_CELLS, 22), (7, SEED7_ACTIONS, SEED7_CELLS, 13)],
)
def test_observed_pacing_and_parking_are_stuck(tmp_path, seed, actions, cells, steps):
    two = SystemTwo(
        FakePlanner(), ThinkConfig(trigger="rule", replan_every=5, cooldown=0), DEFAULT_PREFIX
    )
    path = tmp_path / "ep.jsonl"
    s = run_episode(
        GridWorld(),
        Scripted(actions),
        seed=seed,
        stuck_after=10,
        hooks=two.hooks(),
        record_path=path,
    )
    ep = read_episode(path)
    assert [tuple(t.observation.player) for t in ep.ticks] == cells  # the recorded trajectory
    assert (s.outcome, s.steps) == ("stuck", steps)
    assert (ep.end.stuck_after, ep.end.ticks_without_new_cell) == (10, 10)


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
        view.stuck_streak = (2, 4)
        assert "reversals/ep -   no new cell 2/4" in view._info()
        view.stuck_streak = (1, 0)
        assert "reversals/ep -   no new cell 1" in view._info()
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_n))
        assert view._pump() and view.skip_requested
