"""Story 5.1 — plan calls and plan injection into the memory tail."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import httpx
import pytest

from gridworld.backends.fake import FakeBackend
from gridworld.harness import run_episode
from gridworld.harness.plan import (
    PLAN_INSTRUCTION,
    FakePlanner,
    HTTPPlanner,
    LocalPlanner,
    split_trace,
)
from gridworld.harness.prompts import DEFAULT_PREFIX
from gridworld.harness.think import SystemTwo, ThinkConfig
from gridworld.record import read_episode
from gridworld.render.text import to_text
from gridworld.sim import GridWorld, generate_map


class Spy(FakeBackend):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.requests = []

    def decide(self, request):
        self.requests.append(request)
        return super().decide(request)


def test_split_trace():
    assert split_trace("<|channel>thought\nhmm<channel|>Go west.") == ("hmm", "Go west.", True)
    assert split_trace("<think>a</think> b") == ("a", "b", True)
    assert split_trace("<|channel>thought\nstill thinking") == ("still thinking", "", False)
    assert split_trace("  plain plan ") == (None, "plain plan", True)


def test_start_plan_goes_into_the_tail_and_nothing_else_changes(tmp_path):
    planner = FakePlanner("Go west then north.")
    two = SystemTwo(planner, ThinkConfig(trigger="start"), DEFAULT_PREFIX)
    plain, planned = Spy(), Spy()
    run_episode(GridWorld(), plain, seed=3, max_ticks=4)
    path = tmp_path / "ep.jsonl"
    run_episode(GridWorld(), planned, seed=3, max_ticks=4, hooks=two.hooks(), record_path=path)
    assert len(planner.calls) == 1
    assert planner.calls[0]["state"] == to_text(generate_map(3))
    for a, b in zip(plain.requests, planned.requests, strict=True):
        la, lb = a["state"].split("\n"), b["state"].split("\n")
        assert la[:-1] == lb[:-1] and lb[-1] == la[-1] + " | plan: Go west then north."
        assert {k: v for k, v in a.items() if k != "state"} == {
            k: v for k, v in b.items() if k != "state"
        }
    ticks = read_episode(path).ticks
    assert ticks[0].plan["plan"] == "Go west then north." and ticks[0].plan["truncated"] is False
    assert all(t.plan is None for t in ticks[1:])
    assert ticks[0].timing["think_ms"] >= 0


def test_trace_style_keeps_the_trace_out_of_the_tail(tmp_path):
    planner = FakePlanner("Go west.", trace="secret reasoning")
    two = SystemTwo(planner, ThinkConfig(trigger="start", style="trace"), DEFAULT_PREFIX)
    spy, path = Spy(), tmp_path / "ep.jsonl"
    run_episode(GridWorld(), spy, seed=3, max_ticks=2, hooks=two.hooks(), record_path=path)
    assert all("secret reasoning" not in r["state"] for r in spy.requests)
    assert spy.requests[0]["state"].endswith("plan: Go west.")
    plan = read_episode(path).ticks[0].plan
    assert plan["trace"] == "secret reasoning" and plan["style"] == "trace"


def test_truncated_plan_is_recorded_as_such_and_not_injected(tmp_path):
    planner = FakePlanner(truncated=True)
    two = SystemTwo(
        planner, ThinkConfig(trigger="start", style="trace", max_tokens=64), DEFAULT_PREFIX
    )
    spy, path = Spy(), tmp_path / "ep.jsonl"
    run_episode(GridWorld(), spy, seed=3, max_ticks=2, hooks=two.hooks(), record_path=path)
    plan = read_episode(path).ticks[0].plan
    assert plan["truncated"] is True and plan["finish_reason"] == "length" and plan["plan"] == ""
    assert plan["completion_tokens"] == 64
    assert all("plan:" not in r["state"] for r in spy.requests)


def test_http_planner_request_shape():
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "Go west.",
                            "reasoning_content": "think",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 100, "completion_tokens": 7},
            },
        )

    client = httpx.Client(base_url="http://t", transport=httpx.MockTransport(handler))
    r = HTTPPlanner("http://t", client=client).plan(
        "RULES", "STATE", style="trace", max_tokens=4096
    )
    (body,) = seen
    assert body["max_tokens"] == 4096 and body["enable_thinking"] is True
    assert body["messages"][0] == {"role": "system", "content": "RULES"}
    assert body["messages"][1]["content"] == f"STATE\n\n{PLAN_INSTRUCTION}"
    assert (r.plan, r.trace, r.completion_tokens, r.truncated) == ("Go west.", "think", 7, False)


def test_http_planner_against_the_golden_chat_route_in_process():
    pytest.importorskip("litestar")
    pytest.importorskip("mlx_classifiers")
    from litestar.testing import TestClient
    from mlx_classifiers.runner import FakeRunner
    from mlx_classifiers.server import ChatResult, create_app

    calls = []

    def generate(runner, tokens, cache, max_tokens, temperature):
        calls.append(max_tokens)
        return ChatResult("Go west.", 3, "stop")

    with TestClient(create_app(FakeRunner(), generate=generate)) as client:
        r = HTTPPlanner("http://testserver", client=client).plan(
            DEFAULT_PREFIX, "STATE", style="direct", max_tokens=4096
        )
    assert calls == [4096] and r.plan == "Go west." and r.finish_reason == "stop"


def test_local_planner_from_backend_unwraps_the_prefix_memo():
    class Runner:
        model, tokenizer = "M", "T"

    class Memo:
        runner = Runner()

    class Backend:
        runner, model_id = Memo(), "m"

    p = LocalPlanner.from_backend(Backend())
    assert (p.model, p.tokenizer, p.id) == ("M", "T", "local-plan:m")


@pytest.mark.skipif("GRIDWORLD_SERVER_URL" not in os.environ, reason="set GRIDWORLD_SERVER_URL")
@pytest.mark.server
def test_live_server_plan():
    r = HTTPPlanner(os.environ["GRIDWORLD_SERVER_URL"]).plan(
        DEFAULT_PREFIX, to_text(generate_map(3)), style="direct", max_tokens=256
    )
    assert r.completion_tokens > 0


@pytest.mark.mlx
def test_real_e2b_trace_plan():
    pytest.importorskip("mlx_lm")
    from test_local_backend import _weights_cached

    from gridworld.backends.local import DEFAULT_MODEL, LocalBackend
    from gridworld.harness.provenance import power_state

    if not _weights_cached(DEFAULT_MODEL):
        pytest.skip(f"{DEFAULT_MODEL} not in the HF cache")
    planner = LocalPlanner.from_backend(LocalBackend(DEFAULT_MODEL))
    t0 = time.perf_counter()
    r = planner.plan(DEFAULT_PREFIX, to_text(generate_map(3)), style="trace", max_tokens=4096)
    line = {
        "truncated": r.truncated,
        "finish_reason": r.finish_reason,
        "completion_tokens": r.completion_tokens,
        "wall_s": round(time.perf_counter() - t0, 1),
        "trace_chars": len(r.trace or ""),
        "plan": r.plan,
        "power": power_state(),
    }
    out = os.environ.get("GRIDWORLD_PLAN_SUMMARY")
    if out:
        Path(out).write_text(json.dumps(line) + "\n")
    print(line)
    assert r.completion_tokens > 0
