"""Story 4.4 — memory modes: none, summary, transcript."""

from __future__ import annotations

from itertools import pairwise

from gridworld.backends.fake import FakeBackend
from gridworld.harness import Hooks, run_episode
from gridworld.harness.memory import SummaryMemory, TranscriptMemory, make_memory
from gridworld.harness.session import run_session
from gridworld.sim import GridWorld


class Spy(FakeBackend):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.requests = []

    def decide(self, request):
        self.requests.append(request)
        return super().decide(request)


def test_summary_differs_from_none_only_in_the_status_line_and_names_three_actions():
    none, summ = Spy(), Spy()
    a = run_episode(GridWorld(), none, seed=3, max_ticks=6)
    b = run_episode(GridWorld(), summ, seed=3, max_ticks=6, memory=SummaryMemory(k=3))
    assert a.steps == b.steps == 6
    for t, (ra, rb) in enumerate(zip(none.requests, summ.requests, strict=True)):
        la, lb = ra["state"].split("\n"), rb["state"].split("\n")
        assert la[:-1] == lb[:-1]
        assert lb[-1].startswith(la[-1] + " | recent: ")
    last = summ.requests[-1]["state"].split("\n")[-1]
    recent = last.split(" | recent: ")[1].split(", ")
    assert len(recent) == 3 and all("->(" in r for r in recent)
    assert summ.requests[0]["state"].endswith("recent: none")


def test_transcript_carries_prior_turns_and_cached_tokens_grow():
    backend = Spy(prefix_cache=True)
    cached = []
    run_episode(
        GridWorld(),
        backend,
        seed=3,
        max_ticks=8,
        memory=TranscriptMemory(),
        hooks=Hooks(after_tick=lambda log: cached.append(log.usage["cached_tokens"])),
    )
    for t, req in enumerate(backend.requests):
        state = req["state"] if isinstance(req["state"], list) else [req["state"]]
        assert len(state) == t + 1
        assert all("\nWhich action next? " in turn for turn in state[:-1])
    assert cached[0] == 0 and all(b > a for a, b in pairwise(cached))


def test_transcript_without_a_prefix_cache_reports_no_cached_tokens():
    s = run_episode(GridWorld(), FakeBackend(), seed=3, max_ticks=3, memory=TranscriptMemory())
    assert s.mean_cached_tokens == 0 and s.agreement == 1.0


def test_oscillation_is_reported_per_memory_mode(tmp_path):
    for name in ("none", "summary", "transcript"):
        r = run_session(FakeBackend(noise=0.3, seed=2), memory=name, episodes=3, out_dir=tmp_path)
        assert r.report.meta.memory == name
        assert r.report.summary.distinct_cell_ratio is not None
        assert r.report.summary.reversals_per_episode is not None


def test_make_memory():
    assert make_memory("summary").name == "summary"
    assert make_memory("transcript").history() == []


def test_summary_k_and_visit_counts():
    spy = Spy()
    mem = SummaryMemory(k=10, visits=True)
    run_episode(GridWorld(), spy, seed=3, max_ticks=12, memory=mem)
    first = spy.requests[0]["state"].split("\n")[-1]
    x, y = GridWorld().reset(3).player
    assert first.endswith(f"recent: none | here ({x},{y}) visited 1x; most visited: ({x},{y}) 1")
    last = spy.requests[-1]["state"].split("\n")[-1]
    recent = last.split(" | recent: ")[1].split(" | here ")[0].split(", ")
    assert len(recent) == 10
    assert " | here (" in last and "x; most visited: " in last


def test_visit_counts_on_a_back_and_forth_path():
    from gridworld.sim import Action

    mem = SummaryMemory(visits=True)
    obs = GridWorld().reset(3)
    a = obs
    b = obs.model_copy(update={"player": (obs.player[0] - 1, obs.player[1])})
    for before, after in [(a, b), (b, a), (a, b), (b, a)]:
        mem.observe(before, "", Action.WEST, after)
    tail = mem.tail(a)
    (ax, ay), (bx, by) = a.player, b.player
    assert f"here ({ax},{ay}) visited 3x; most visited: ({ax},{ay}) 3, ({bx},{by}) 2" in tail


def test_memory_knobs_reach_the_report(tmp_path):
    import json

    from gridworld import cli

    out = tmp_path / "runs"
    argv = ["play", "--episodes", "1", "--memory", "summary", "--memory-k", "10"]
    assert cli.main([*argv, "--memory-visits", "--out", str(out)]) == 0
    (js,) = out.glob("*.json")
    meta = json.loads(js.read_text())["meta"]
    assert (meta["memory_k"], meta["memory_visits"]) == (10, True)
    assert js.name.endswith("-summary-k10-visits.json")
