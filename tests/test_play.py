"""Story 4.3 — play CLI, headless CI run with the fake backend, continuous mode."""

from __future__ import annotations

import json
import sys

import pytest

from gridworld import cli
from gridworld.backends.fake import FakeBackend
from gridworld.harness import Hooks
from gridworld.harness.memory import MEMORY_MODES
from gridworld.harness.session import run_session
from gridworld.record import read_episode


def report_json(out):
    (path,) = out.glob("*.json")
    return json.loads(path.read_text())


@pytest.mark.parametrize("mode", ["text", "image"])
@pytest.mark.parametrize("memory", sorted(MEMORY_MODES))
def test_ci_five_fake_episodes(tmp_path, capsys, mode, memory):
    out = tmp_path / "runs"
    argv = ["play", "--backend", "fake", "--mode", mode, "--memory", memory]
    assert cli.main([*argv, "--episodes", "5", "--seed", "0", "--out", str(out)]) == 0
    data = report_json(out)
    assert data["meta"]["mode"] == mode and data["meta"]["memory"] == memory
    assert data["summary"]["episodes"] == 5 and data["summary"]["agreement"] == 1.0
    assert data["summary"]["distinct_cell_ratio"] is not None
    assert all("reversals" in e for e in data["episodes"])
    assert len(list(out.glob("*.md"))) == 1
    assert len(list(next(out.glob("*/")).glob("seed-*.jsonl"))) == 5
    assert "| oracle agreement | 100.0% |" in capsys.readouterr().out


def test_world_flags_reach_header_and_report(tmp_path):
    out = tmp_path / "runs"
    argv = ["play", "--episodes", "1", "--out", str(out), "--width", "12", "--height", "8"]
    argv += ["--monsters", "3", "--walls", "0.1", "--hp", "9", "--tick-limit", "150"]
    assert cli.main(argv) == 0
    cfg = report_json(out)["meta"]["config"]
    assert cfg == {
        "width": 12,
        "height": 8,
        "wall_density": 0.1,
        "n_monsters": 3,
        "player_hp": 9,
        "monster_hp": 2,
        "sight_radius": 4,
        "tick_limit": 150,
    }
    (ep,) = next(out.glob("*/")).glob("seed-*.jsonl")
    assert read_episode(ep).header.config.model_dump() == cfg


def test_continuous_mode_stops_after_three_episodes(tmp_path):
    played = []

    def stop_after_three(summary):
        played.append(summary.seed)
        return len(played) < 3

    result = run_session(
        FakeBackend(), episodes=0, seed=10, out_dir=tmp_path, on_episode=stop_after_three
    )
    assert played == [10, 11, 12]
    assert len(list(result.episode_dir.glob("seed-*.jsonl"))) == 3
    assert len(list(tmp_path.glob("*.md"))) == 1 and len(list(tmp_path.glob("*.json"))) == 1
    assert result.report.summary.episodes == 3 and not result.report.meta.interrupted


def test_keyboard_interrupt_still_writes_the_report(tmp_path):
    ticks = []

    def interrupt(log):
        ticks.append(log)
        if len(ticks) == 30:
            raise KeyboardInterrupt

    result = run_session(
        FakeBackend(), episodes=0, out_dir=tmp_path, hooks=Hooks(after_tick=interrupt)
    )
    assert result.report.meta.interrupted and result.json.exists()
    files = sorted(result.episode_dir.glob("seed-*.jsonl"))
    assert len(files) == result.report.summary.episodes + 1
    assert read_episode(files[-1]).end.reason == "stopped"


def test_view_without_pygame_names_the_extra(monkeypatch, capsys, tmp_path):
    monkeypatch.setitem(sys.modules, "pygame", None)
    assert cli.main(["play", "--view", "--episodes", "1", "--out", str(tmp_path)]) == 2
    assert "systemone-gridworld[view]" in capsys.readouterr().err


def test_continuous_view_headless_shows_tallies_and_flash(monkeypatch, tmp_path):
    pytest.importorskip("pygame")
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    from gridworld.view import LiveView

    flashes = []

    class Watched(LiveView):
        def flash(self, text, seconds=1.0, obs=None):
            flashes.append((text, list(self.info_lines)))
            return super().flash(text, 0, obs)

    with Watched(scale=1) as view:
        run_session(FakeBackend(), episodes=2, seed=3, out_dir=tmp_path, view=view, flash_s=0)
    assert [f[0] for f in flashes] == ["seed 3: WON", "seed 4: WON"]
    assert flashes[-1][1][1].startswith("episodes 2   win 100%")
