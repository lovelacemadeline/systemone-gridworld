"""Story 5.5 — the planner on a different model (or server) than the decider."""

from __future__ import annotations

import argparse
import json

import httpx

from gridworld import cli
from gridworld.harness import plan as plan_mod
from gridworld.harness.plan import HTTPPlanner, LocalPlanner
from gridworld.record import read_episode

BIG = "mlx-community/gemma-4-26B-A4B-it-qat-4bit"


def test_from_repo_loads_a_separate_runner():
    loaded = []

    class Runner:
        model, tokenizer, model_id = "BIG-M", "BIG-T", BIG

    def loader(repo):
        loaded.append(repo)
        return Runner()

    p = LocalPlanner.from_repo(BIG, loader=loader)
    assert loaded == [BIG] and (p.model, p.tokenizer) == ("BIG-M", "BIG-T")
    assert p.model_id == BIG and p.id == f"local-plan:{BIG}"


def args(**kw):
    base = {
        "backend": "local",
        "plan_backend": None,
        "plan_model": None,
        "plan_url": None,
        "url": "http://decider:8080",
    }
    return argparse.Namespace(**(base | kw))


def test_planner_selection(monkeypatch):
    monkeypatch.setattr(LocalPlanner, "from_repo", classmethod(lambda cls, repo: ("repo", repo)))
    monkeypatch.setattr(LocalPlanner, "from_backend", classmethod(lambda cls, b: ("shared", b)))
    assert cli._planner(args(plan_model=BIG), "decider") == ("repo", BIG)
    assert cli._planner(args(), "decider") == ("shared", "decider")
    p = cli._planner(
        args(backend="fake", plan_backend="http", plan_url="http://planner:8081"), None
    )
    assert isinstance(p, HTTPPlanner) and p.id == "http-plan:http://planner:8081"
    p = cli._planner(args(backend="http"), None)
    assert p.id == "http-plan:http://decider:8080"


def test_flag_errors(capsys, tmp_path):
    assert cli.main(["play", "--backend", "fake", "--plan-model", BIG, "--out", str(tmp_path)]) == 2
    assert "--plan-model needs a local planner" in capsys.readouterr().err
    assert cli.main(["play", "--plan-url", "http://x", "--out", str(tmp_path)]) == 2
    assert "--plan-url needs --plan-backend http" in capsys.readouterr().err


def test_separate_plan_server_ids_reach_header_and_report(monkeypatch, tmp_path):
    bodies = []

    def handler(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "model": BIG,
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "Go west.",
                            "reasoning": "thinking",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 50, "completion_tokens": 5},
            },
        )

    real = HTTPPlanner

    class Mocked(real):
        def __init__(self, base_url, **kw):
            client = httpx.Client(base_url=base_url, transport=httpx.MockTransport(handler))
            super().__init__(base_url, client=client)

    monkeypatch.setattr(plan_mod, "HTTPPlanner", Mocked)
    out = tmp_path / "runs"
    argv = ["play", "--backend", "fake", "--episodes", "2", "--think", "start", "--plan", "trace"]
    argv += ["--plan-backend", "http", "--plan-url", "http://planner:8081", "--out", str(out)]
    assert cli.main(argv) == 0
    assert len(bodies) == 2 and all(b["enable_thinking"] for b in bodies)
    (js,) = out.glob("*.json")
    meta = json.loads(js.read_text())["meta"]
    assert meta["planner"] == "http-plan:http://planner:8081" and meta["planner_model"] == BIG
    assert meta["backend"] == "fake(noise=0)"
    ep = read_episode(next(next(out.glob("*/")).glob("seed-*.jsonl")))
    assert ep.header.planner == "http-plan:http://planner:8081"
    assert ep.ticks[0].plan["trace"] == "thinking" and ep.ticks[0].plan["plan"] == "Go west."
