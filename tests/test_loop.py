"""Story 4.1 — the episode loop and its decision log."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from gridworld.backends.fake import FakeBackend
from gridworld.harness import Hooks, run_episode
from gridworld.harness.prompts import DEFAULT_PREFIX, load_prefix
from gridworld.record import read_episode, replay
from gridworld.sim import GridWorld

PHASES = {"render_ms", "backend_ms", "think_ms", "step_ms", "total_ms"}


def test_fake_episode_records_one_line_per_tick_and_terminates(tmp_path):
    path = tmp_path / "ep.jsonl"
    s = run_episode(GridWorld(), FakeBackend(), seed=3, record_path=path)
    ep = read_episode(path)
    assert len(ep.ticks) == s.steps > 0
    assert ep.end is not None and s.outcome == "won"
    assert ep.header.backend == "fake(noise=0)" and ep.header.mode == "text"
    for t in ep.ticks:
        assert set(t.timing) == PHASES and t.probabilities and t.usage["output_tokens"] == 0
        assert t.timing["total_ms"] >= t.timing["backend_ms"]
    assert len(list(replay(path))) == s.steps + 1


def test_noise_free_fake_agrees_and_matches_oracle_steps():
    s = run_episode(GridWorld(), FakeBackend(), seed=5)
    assert s.agreement == 1.0 and s.steps == s.oracle_steps and s.steps_over_oracle == 1.0


def test_image_mode_episode(tmp_path):
    path = tmp_path / "ep.jsonl"
    s = run_episode(GridWorld(), FakeBackend(), seed=2, mode="image", record_path=path)
    assert s.outcome == "won" and read_episode(path).header.mode == "image"


def test_max_ticks_cuts_the_episode_short_and_still_replays(tmp_path):
    path = tmp_path / "ep.jsonl"
    s = run_episode(GridWorld(), FakeBackend(), seed=3, record_path=path, max_ticks=4)
    assert (s.outcome, s.steps) == ("max_ticks", 4)
    assert read_episode(path).end.reason == "max_ticks"
    assert len(list(replay(path))) == 5


def test_hooks_inject_text_and_see_every_tick():
    seen_requests, ticks = [], []

    class Spy(FakeBackend):
        def decide(self, request):
            seen_requests.append(request)
            return super().decide(request)

    hooks = Hooks(
        before_decision=lambda obs, t: "plan: go east" if t == 0 else None, after_tick=ticks.append
    )
    s = run_episode(GridWorld(), Spy(), seed=3, hooks=hooks)
    assert seen_requests[0]["state"].endswith(" | plan: go east")
    assert not seen_requests[1]["state"].endswith("plan: go east")
    assert len(ticks) == s.steps


def test_view_closing_stops_the_episode():
    class View:
        calls = 0

        def update(self, *args):
            View.calls += 1
            return View.calls < 3

    s = run_episode(GridWorld(), FakeBackend(), seed=3, view=View())
    assert (s.outcome, s.steps) == ("stopped", 3)


def test_prefix_is_sent_and_overridable(tmp_path):
    sent = []

    class Spy(FakeBackend):
        def decide(self, request):
            sent.append(request["prefix"])
            return super().decide(request)

    run_episode(GridWorld(), Spy(), seed=3, max_ticks=1)
    f = tmp_path / "p.txt"
    f.write_text("Custom rules.\n")
    run_episode(GridWorld(), Spy(), seed=3, max_ticks=1, prefix=load_prefix(f))
    assert sent == [DEFAULT_PREFIX, "Custom rules."]


@pytest.mark.mlx
def test_real_e2b_episode(tmp_path):
    pytest.importorskip("mlx_lm")
    from test_local_backend import _weights_cached

    from gridworld.backends.local import DEFAULT_MODEL, LocalBackend
    from gridworld.harness.provenance import power_state

    if not _weights_cached(DEFAULT_MODEL):
        pytest.skip(f"{DEFAULT_MODEL} not in the HF cache")
    backend = LocalBackend(DEFAULT_MODEL)
    path = tmp_path / "e2b.jsonl"
    s = run_episode(GridWorld(), backend, seed=3, record_path=path, max_ticks=60)
    assert s.steps == len(read_episode(path).ticks)
    line = {
        "outcome": s.outcome,
        "steps": s.steps,
        "oracle_steps": s.oracle_steps,
        "agreement": round(s.agreement, 3),
        "decisions_per_s": round(s.decisions_per_s, 2),
        "p50_total_ms": round(s.p50_total_ms, 1),
        "power": power_state(),
    }
    out = os.environ.get("GRIDWORLD_E2B_SUMMARY")
    if out:
        Path(out).write_text(json.dumps(line) + "\n")
    print(line)
