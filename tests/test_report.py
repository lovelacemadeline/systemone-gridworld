"""Story 4.2 — scoring and the run report."""

from __future__ import annotations

import json

from gridworld.backends.fake import FakeBackend
from gridworld.harness import run_episode
from gridworld.harness.prompts import DEFAULT_PREFIX
from gridworld.harness.provenance import power_state
from gridworld.harness.report import (
    RunMeta,
    build_report,
    prefix_digest,
    run_name,
    utc_stamp,
    write_report,
)
from gridworld.harness.score import oscillation, summarize_run
from gridworld.sim import GridWorld


def fake_run(noise: float, n: int = 5):
    backend = FakeBackend(noise=noise, seed=1)
    return backend, [run_episode(GridWorld(), backend, seed=s) for s in range(n)]


def meta_for(backend, name="test-run"):
    return RunMeta(
        name=name,
        backend=backend.id,
        model=getattr(backend, "model_id", None),
        mode="text",
        memory="none",
        git_rev="abc1234",
        power=power_state(),
        config=GridWorld().config,
        prefix_chars=len(DEFAULT_PREFIX),
        prefix_sha256=prefix_digest(DEFAULT_PREFIX),
        started=utc_stamp(),
    )


def test_noise_orders_agreement_and_completion():
    clean = summarize_run(fake_run(0.0)[1])
    noisy = summarize_run(fake_run(0.3)[1])
    assert clean.agreement == 1.0 > noisy.agreement
    assert clean.completion >= noisy.completion
    assert clean.steps_over_oracle == 1.0


def test_run_summary_fields():
    _, eps = fake_run(0.0)
    s = summarize_run(eps)
    assert s.episodes == 5 and s.ticks == sum(e.steps for e in eps)
    assert s.p50_total_ms <= s.p95_total_ms and s.decisions_per_s > 0
    assert s.tokens_per_observation > 0 and 0.6 <= s.mean_top_probability <= 0.95
    assert s.distinct_cell_ratio is not None and s.reversals_per_episode is not None


def test_oscillation():
    assert oscillation([(0, 0), (1, 0), (2, 0)]) == (1.5, 0)
    ratio, reversals = oscillation([(0, 0), (1, 0), (0, 0), (1, 0), (1, 0)])
    assert (ratio, reversals) == (0.5, 2)


def test_report_files_carry_provenance(tmp_path):
    backend, eps = fake_run(0.3)
    md, js = write_report(build_report(meta_for(backend), eps), tmp_path)
    data = json.loads(js.read_text())
    assert data["meta"]["backend"] == "fake(noise=0.3)" and data["meta"]["git_rev"] == "abc1234"
    assert set(data["meta"]["power"]) == {"low_power_mode", "power_source"}
    assert len(data["episodes"]) == 5 and "agreement" in data["summary"]
    text = md.read_text()
    assert "| oracle agreement |" in text and "| distinct cells / steps |" in text
    assert text.count("\n| ") >= 5 + 16


def test_run_name_is_filesystem_safe():
    name = run_name("http:http://127.0.0.1:8080", "text", "none", stamp="20261016T120000Z")
    assert name == "20261016T120000Z-http-http-127.0.0.1-8080-text-none"
