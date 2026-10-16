"""Story 3.2 — fake backend: the oracle with controllable noise."""

from __future__ import annotations

import pytest

from gridworld.backends import build_request, call, make_backend
from gridworld.backends.fake import FakeBackend
from gridworld.oracle import oracle
from gridworld.render.text import parse_text, to_text
from gridworld.sim import GridWorld, generate_map


def run(backend, seed, mode="text"):
    """Play one episode through the adapter; return (agreements, ticks, decisions)."""
    world = GridWorld()
    obs = world.reset(seed)
    agree, decisions = 0, []
    while True:
        d = call(backend, build_request(obs, mode=mode).request)
        decisions.append(d)
        agree += d.action is oracle(obs)
        r = world.step(d.action)
        obs = r.observation
        if r.done:
            return agree, len(decisions), decisions


def test_noise_zero_agrees_with_the_oracle_on_every_tick():
    backend = FakeBackend(noise=0.0)
    for seed in range(20):
        agree, ticks, _ = run(backend, seed)
        assert agree == ticks


def test_image_mode_reads_the_text_block():
    agree, ticks, _ = run(FakeBackend(), 4, mode="image")
    assert agree == ticks


def test_noise_lowers_agreement():
    rates = []
    for noise in (0.0, 0.3, 1.0):
        backend = FakeBackend(noise=noise, seed=1)
        agree = ticks = 0
        for seed in range(10):
            a, t, _ = run(backend, seed)
            agree, ticks = agree + a, ticks + t
        rates.append(agree / ticks)
    assert rates[0] == 1.0 > rates[1] > rates[2] == 0.0


def test_probabilities_are_plausible():
    _, _, decisions = run(FakeBackend(noise=0.2, seed=3), 2)
    for d in decisions:
        top = d.probabilities[d.action]
        assert 0.6 <= top <= 0.95 and d.confidence == top
        assert sum(d.probabilities.values()) == pytest.approx(1.0)
        assert max(d.probabilities.values()) == top
        assert d.usage["output_tokens"] == 0 and d.usage["input_tokens"] > 0


def test_latency_is_reported_exactly_and_slept():
    d = call(FakeBackend(latency_s=0.02), build_request(generate_map(0)).request)
    assert d.timing_ms == {"total": 20.0}
    assert d.wall_ms >= 20.0


def test_same_seed_same_answers():
    a = [d.response for d in run(FakeBackend(noise=0.5, seed=9), 1)[2]]
    b = [d.response for d in run(FakeBackend(noise=0.5, seed=9), 1)[2]]
    assert a == b


def test_parse_text_inverts_to_text():
    for seed in range(20):
        obs = generate_map(seed)
        assert parse_text(to_text(obs)) == obs.model_copy(update={"seed": 0})
    with pytest.raises(ValueError):
        parse_text("hello")


def test_registry_builds_the_fake():
    b = make_backend("fake", noise=0.1)
    assert isinstance(b, FakeBackend) and b.id == "fake(noise=0.1)"
    with pytest.raises(ValueError, match="unknown backend"):
        make_backend("nope")
