"""Story 2.4 — live view: frame composition (pure Pillow) and the headless pygame shell."""

from __future__ import annotations

import sys

import pytest
from PIL import Image

from gridworld import cli
from gridworld.oracle import oracle
from gridworld.record import EpisodeHeader, EpisodeRecorder, read_episode, record_episode
from gridworld.render.image import to_image
from gridworld.render.tiles import ACTION_COLOURS
from gridworld.sim import Action, GridWorld, generate_map
from gridworld.view import (
    BAR_OTHER,
    ORACLE_OUTLINE,
    DecisionRate,
    ViewUnavailable,
    render_frame,
)

BAR_X0 = 12 + 56  # panel offsets in render_frame


def bar_row(frame: Image.Image, board_w: int, i: int) -> list[tuple[int, int, int]]:
    y = 60 + i * 28 + 8
    return [frame.getpixel((board_w + BAR_X0 + dx, y)) for dx in range(260 - 56 - 24)]


@pytest.fixture
def headless(monkeypatch):
    pytest.importorskip("pygame")
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")


@pytest.fixture
def episode(tmp_path):
    """A real oracle episode with probabilities and timing, as a backend run would record."""
    path = tmp_path / "ep.jsonl"
    world = GridWorld()
    obs = world.reset(3)
    header = EpisodeHeader(seed=3, config=world.config, backend="fake", mode="text")
    with EpisodeRecorder(path, header) as rec:
        while True:
            action = oracle(obs)
            probs = {a: (0.75 if a is action else 0.05) for a in Action}
            rec.tick(obs, action, action, probs, timing={"backend": 40.0, "render": 10.0})
            result = world.step(action)
            obs = result.observation
            if result.done:
                rec.end(obs, result.reward, result.info["reason"])
                return path


def test_map_is_the_image_renderer_scaled_up():
    obs = generate_map(3)
    frame = render_frame(obs, scale=2)
    board = to_image(obs).resize((320, 384), Image.Resampling.NEAREST)
    assert frame.crop((0, 0, 320, 384)).tobytes() == board.tobytes()


def test_bars_follow_probabilities_and_colour_the_taken_action():
    obs = generate_map(3)
    probs = {"north": 0.5, "south": 0.25, "east": 0.0, "west": 0.0, "attack": 0.0, "wait": 0.25}
    frame = render_frame(obs, probabilities=probs, action=Action.NORTH, scale=1)
    north, south = bar_row(frame, 160, 0), bar_row(frame, 160, 1)
    assert north.count(ACTION_COLOURS[Action.NORTH]) == 90
    assert south.count(BAR_OTHER) == 45


def test_oracle_action_is_outlined():
    obs = generate_map(3)
    frame = render_frame(obs, oracle_action=Action.ATTACK, scale=1)
    y = 60 + 4 * 28 - 2
    assert frame.getpixel((160 + BAR_X0 + 20, y)) == ORACLE_OUTLINE
    assert frame.getpixel((160 + BAR_X0 + 20, 60 + 3 * 28 - 2)) != ORACLE_OUTLINE


def test_decision_rate_uses_total_else_sum_of_phases():
    rate = DecisionRate()
    assert rate.per_second is None
    rate.add(None)
    rate.add({"backend": 40.0, "render": 10.0})
    rate.add({"total": 50.0, "backend": 1.0})
    assert rate.per_second == pytest.approx(20.0)


def test_play_file_headless(headless, episode):
    from gridworld.view import play_file

    shown = play_file(episode, fps=0, flash_s=0)
    ep = read_episode(episode)
    assert shown == len(ep.ticks) + 1


def test_live_view_blits_the_frame_and_tracks_decisions(headless, episode):
    from gridworld.view import LiveView

    ep = read_episode(episode)
    with LiveView(scale=1) as view:
        for t in ep.ticks[:5]:
            assert view.update(t.observation, t.probabilities, t.action, t.oracle_action, t.timing)
        surface = view._screen
        frame = view.last_frame
        assert surface.get_size() == frame.size
        assert tuple(surface.get_at((5, 5)))[:3] == frame.getpixel((5, 5))
        assert view.rate.per_second == pytest.approx(20.0)


def test_missing_pygame_names_the_extra(monkeypatch):
    from gridworld.view import LiveView

    monkeypatch.setitem(sys.modules, "pygame", None)
    with pytest.raises(ViewUnavailable, match=r"\[view\]"):
        LiveView()


def test_cli_view_without_pygame_exits_2(monkeypatch, capsys, episode):
    monkeypatch.setitem(sys.modules, "pygame", None)
    assert cli.main(["view", str(episode), "--no-hold"]) == 2
    assert "systemone-gridworld[view]" in capsys.readouterr().err


def test_cli_oracle_then_view(headless, tmp_path, capsys):
    path = tmp_path / "oracle.jsonl"
    assert cli.main(["oracle", "--seed", "3", "--out", str(path)]) == 0
    assert cli.main(["view", str(path), "--fps", "0", "--no-hold", "--flash", "0"]) == 0
    assert "frames" in capsys.readouterr().out


def test_record_episode_records_a_replayable_oracle_run(tmp_path):
    from gridworld.record import replay

    path = tmp_path / "ep.jsonl"
    result = record_episode(path, 5)
    ep = read_episode(path)
    assert ep.end.reason == result.info["reason"]
    assert all(t.action is t.oracle_action and t.probabilities is None for t in ep.ticks)
    assert len(list(replay(path))) == len(ep.ticks) + 1
