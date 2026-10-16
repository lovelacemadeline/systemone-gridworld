"""Story 3.3 — in-process backend over mlx-classifiers decide()."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

pytest.importorskip("mlx_classifiers")
from mlx_classifiers.fitting import CalibrationConfig
from mlx_classifiers.runner import FakeRunner

from gridworld.backends import build_request, call, make_backend
from gridworld.backends.local import DEFAULT_MODEL, LocalBackend
from gridworld.sim import Action, GridWorld, generate_map

HF_HUB = Path.home() / ".cache" / "huggingface" / "hub"


def fake_local() -> LocalBackend:
    return LocalBackend(runner=FakeRunner(), calibration=CalibrationConfig())


def test_one_tick_validates_with_zero_output_tokens():
    d = call(fake_local(), build_request(generate_map(3)).request)
    assert d.action in Action and d.usage["output_tokens"] == 0
    assert sum(d.probabilities.values()) == pytest.approx(1.0)


def test_prefix_cache_is_reused_across_ticks():
    backend = fake_local()
    world = GridWorld()
    obs = world.reset(1)
    cached = []
    for _ in range(3):
        d = call(backend, build_request(obs, prefix="Stable rules. " * 20).request)
        cached.append(d.usage.get("cached_tokens", 0))
        obs = world.step(d.action).observation
    assert backend.runner.misses == 1 and backend.runner.hits == 2
    assert cached[0] > 0 and len(set(cached)) == 1


def test_image_mode_is_not_implemented():
    req = build_request(generate_map(3), mode="image").request
    with pytest.raises(NotImplementedError, match="image mode"):
        fake_local().decide(req)


def test_registry_passes_kwargs_through():
    b = make_backend("local", runner=FakeRunner(), calibration=CalibrationConfig())
    assert b.id == "local:fake"


def _weights_cached(repo: str) -> bool:
    snaps = HF_HUB / f"models--{repo.replace('/', '--')}" / "snapshots"
    return any((s / "config.json").exists() for s in snaps.glob("*")) if snaps.exists() else False


@pytest.mark.mlx
def test_real_model_one_tick(capsys):
    pytest.importorskip("mlx_lm")
    if not _weights_cached(DEFAULT_MODEL):
        pytest.skip(f"{DEFAULT_MODEL} not in the HF cache")
    t0 = time.perf_counter()
    backend = LocalBackend(DEFAULT_MODEL)
    load_s = time.perf_counter() - t0
    world = GridWorld()
    obs = world.reset(3)
    walls = []
    for _ in range(3):
        d = call(backend, build_request(obs).request)
        walls.append((d.wall_ms, d.usage))
        obs = world.step(d.action).observation
    assert d.usage["output_tokens"] == 0 and d.usage["input_tokens"] > 0
    with capsys.disabled():
        print(f"\nload {load_s:.1f}s; ticks (wall ms, usage): {walls}")
