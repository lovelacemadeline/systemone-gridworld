"""Story 4.8 — the rules prefix edited live: hot reload, versions, and the P key."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from gridworld.backends.fake import FakeBackend
from gridworld.harness import Hooks, prompts
from gridworld.harness.plan import FakePlanner
from gridworld.harness.prompts import DEFAULT_PREFIX, PrefixSource, edit_prefix
from gridworld.harness.session import run_session
from gridworld.harness.think import ThinkConfig
from gridworld.record import read_episode

NEW = "Edited rules: go straight for G."


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def rewrite(path: Path, text: str) -> None:
    """Write ``text`` and push the mtime forward (coarse filesystem clocks)."""
    old = path.stat().st_mtime_ns
    path.write_text(text + "\n", encoding="utf-8")
    bumped = old + 5_000_000_000
    os.utime(path, ns=(bumped, bumped))


class Spy(FakeBackend):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.prefixes: list[str] = []

    def decide(self, request):
        self.prefixes.append(request["prefix"])
        return super().decide(request)


def test_reload_follows_mtime_and_bumps_version_only_on_change(tmp_path):
    f = tmp_path / "p.txt"
    f.write_text("Rules one.\n")
    src = PrefixSource(path=f)
    assert (src.current(), src.version, src.kind) == ("Rules one.", 1, "file")
    assert src.sha256 == sha("Rules one.")
    rewrite(f, "Rules one.")  # touched, same text: no new version
    assert (src.current(), src.version) == ("Rules one.", 1)
    rewrite(f, "Rules two.")
    assert (src.current(), src.version, src.sha256) == ("Rules two.", 2, sha("Rules two."))
    assert [v["version"] for v in src.versions] == [1, 2]
    f.unlink()  # an editor mid-save: keep the last text
    assert (src.current(), src.version) == ("Rules two.", 2)
    fixed = PrefixSource(DEFAULT_PREFIX)
    assert (fixed.current(), fixed.version, fixed.kind) == (DEFAULT_PREFIX, 1, "default")


def test_reload_lands_in_records_and_report(tmp_path):
    f = tmp_path / "p.txt"
    f.write_text("Rules one.\n")
    src = PrefixSource(path=f)

    def after(log):
        if log.observation.tick == 2:
            rewrite(f, NEW)

    spy = Spy()
    result = run_session(
        spy,
        prefix=src,
        episodes=1,
        seed=3,
        out_dir=tmp_path / "runs",
        max_ticks=6,
        hooks=Hooks(after_tick=after),
    )
    (path,) = result.episode_dir.glob("*.jsonl")
    ep = read_episode(path)
    assert ep.header.prefix_sha256 == sha("Rules one.")
    assert [t.prefix_reloaded for t in ep.ticks] == [None, None, None, 2, None, None]
    assert spy.prefixes[:3] == ["Rules one."] * 3 and spy.prefixes[3:] == [NEW] * 3
    meta = result.report.meta
    assert [(v["version"], v["sha256"]) for v in meta.prefix_versions] == [
        (1, sha("Rules one.")),
        (2, sha(NEW)),
    ]
    md = result.md.read_text()
    assert f"versions v1 {sha('Rules one.')[:12]}, v2 {sha(NEW)[:12]}" in md


def test_edit_prefix_with_a_file_opens_it_and_writes_nothing(tmp_path):
    f = tmp_path / "mine.txt"
    f.write_text("Mine.\n")
    src = PrefixSource(path=f)
    opened = []
    assert edit_prefix(src, tmp_path / "session", opener=opened.append) == f
    assert opened == [f] and not (tmp_path / "session").exists()


def test_platform_opener(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(prompts.subprocess, "Popen", lambda cmd, **kw: calls.append(cmd))
    monkeypatch.setattr(prompts.sys, "platform", "darwin")
    prompts.open_with_platform(tmp_path / "a.txt")
    monkeypatch.setattr(prompts.sys, "platform", "linux")
    prompts.open_with_platform(tmp_path / "a.txt")
    assert [c[0] for c in calls] == ["open", "xdg-open"]


def test_p_key_writes_default_once_switches_and_reaches_the_planner(monkeypatch, tmp_path):
    pytest.importorskip("pygame")
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    from gridworld.view import LiveView

    opened: list[tuple[Path, str]] = []
    monkeypatch.setattr(prompts, "open_with_platform", lambda p: opened.append((p, p.read_text())))
    panel: dict[int, list[str]] = {}

    class Watch(LiveView):
        def update(self, obs, *a, **kw):
            pg = self._pg
            if obs.tick in (1, 2):  # P twice: the file is written only once
                pg.event.post(pg.event.Event(pg.KEYDOWN, key=pg.K_p))
            if obs.tick == 3 and opened:
                rewrite(opened[0][0], NEW)
            ok = super().update(obs, *a, **kw)
            panel[obs.tick] = self.prefix_lines()
            return ok

    planner = FakePlanner("Go.")
    think = ThinkConfig(trigger="rule", replan_every=1, cooldown=0)
    with Watch(scale=1) as view:
        result = run_session(
            FakeBackend(),
            episodes=1,
            seed=3,
            out_dir=tmp_path / "runs",
            view=view,
            flash_s=0,
            max_ticks=6,
            think=think,
            planner=planner,
        )
    expected = result.episode_dir / "prefix.txt"
    assert [p for p, _ in opened] == [expected, expected]
    assert opened[0][1] == DEFAULT_PREFIX + "\n"
    assert view.prefix.kind == "file" and view.prefix.version == 2
    assert panel[0] == ["prefix v1 (default)"]
    assert panel[2] == ["prefix v1 (file)"]
    assert panel[4] == ["prefix v2 (file)", "prefix reloaded at tick 4"]
    prefixes = [c["prefix"] for c in planner.calls]
    assert prefixes[:4] == [DEFAULT_PREFIX] * 4 and prefixes[4:] == [NEW] * 2
    (path,) = result.episode_dir.glob("*.jsonl")
    assert read_episode(path).ticks[4].prefix_reloaded == 2


def test_cli_prefix_file_is_a_hot_source(tmp_path, capsys):
    from gridworld import cli

    f = tmp_path / "p.txt"
    f.write_text("CLI rules.\n")
    out = tmp_path / "runs"
    assert cli.main(["play", "--episodes", "1", "--prefix", str(f), "--out", str(out)]) == 0
    (ep,) = out.glob("*/*.jsonl")
    assert read_episode(ep).header.prefix_sha256 == sha("CLI rules.")
    assert cli.main(["play", "--prefix", str(tmp_path / "missing.txt"), "--out", str(out)]) == 2
    assert "--prefix" in capsys.readouterr().err
