"""Story 3.3 — in-process backend over mlx-classifiers decide(); story 3.5 — image mode."""

from __future__ import annotations

import base64
import hashlib
import time
from pathlib import Path

import pytest

pytest.importorskip("mlx_classifiers")
from mlx_classifiers.fitting import CalibrationConfig
from mlx_classifiers.runner import FakeRunner

from gridworld import cli
from gridworld.backends import build_request, call, make_backend
from gridworld.backends.local import DEFAULT_MODEL, LocalBackend
from gridworld.backends.schema import validate_response
from gridworld.harness import run_episode
from gridworld.record import read_episode
from gridworld.render.image import to_png
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


class EncodingFake(FakeRunner):
    """FakeRunner plus the MLXRunner's ``vision_encode_ms`` log: one entry per new image."""

    def __init__(self, ms: float = 7.0) -> None:
        super().__init__()
        self.vision_encode_ms: list[float] = []
        self._seen: set[str] = set()
        self._ms = ms

    def prefill(self, tokens, prefix_cache=None, positions=None, **kw):
        for slot in kw.get("images") or ():
            if slot.sha256 not in self._seen:
                self._seen.add(slot.sha256)
                self.vision_encode_ms.append(self._ms)
        return super().prefill(tokens, prefix_cache, positions, **kw)


def test_image_tick_validates_and_reports_the_encoder():
    backend = LocalBackend(runner=EncodingFake(), calibration=CalibrationConfig())
    req = build_request(generate_map(3), mode="image").request
    wire = backend.decide(req)
    validate_response(wire)
    assert wire["timing_ms"]["encoder"] == 7.0  # one new image encoded
    assert backend.decide(req)["timing_ms"]["encoder"] == 0  # memoised by sha256
    text = backend.decide(build_request(generate_map(3)).request)
    assert "encoder" not in (text.get("timing_ms") or {})


def test_the_image_changes_the_answer_on_the_fake_runner():
    backend = fake_local()
    a = call(backend, build_request(generate_map(3), mode="image").request)
    b = call(backend, build_request(generate_map(3), mode="image", image_only=True).request)
    t = call(backend, build_request(generate_map(3)).request)
    assert a.probabilities != t.probabilities and b.probabilities != a.probabilities


def test_image_episode_records_frame_sha256_and_encoder_ms(tmp_path):
    backend = LocalBackend(runner=EncodingFake(), calibration=CalibrationConfig())
    path = tmp_path / "ep.jsonl"
    run_episode(GridWorld(), backend, seed=3, mode="image", record_path=path, max_ticks=3)
    ep = read_episode(path)
    assert ep.header.mode == "image" and len(ep.ticks) == 3
    for t in ep.ticks:
        assert t.frame_sha256 == hashlib.sha256(to_png(t.observation)).hexdigest()
        assert t.timing["encoder_ms"] in (0.0, 7.0)
    assert ep.ticks[0].timing["encoder_ms"] == 7.0


def test_image_request_carries_one_image_block():
    req = build_request(generate_map(3), mode="image").request
    blocks = [b for b in req["state"] if isinstance(b, dict)]
    assert len(blocks) == 1 and base64.b64decode(blocks[0]["base64"]).startswith(b"\x89PNG")


def test_label_style_alone_is_not_mistaken_for_image_mode():
    req = build_request(generate_map(3), label_style="option-text").request
    try:  # FakeRunner's toy tokenizer may reject word labels; that is not the point here
        fake_local().decide(req)
    except Exception as exc:  # noqa: BLE001
        assert "image mode" not in str(exc)


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


@pytest.mark.mlx
def test_real_model_one_image_tick(capsys, tmp_path):
    pytest.importorskip("mlx_lm")
    try:
        import mlx_classifiers.vision  # noqa: F401
    except ImportError as exc:
        pytest.skip(f"mlx-classifiers vision path unavailable: {exc}")
    if not _weights_cached(DEFAULT_MODEL):
        pytest.skip(f"{DEFAULT_MODEL} not in the HF cache")
    backend = LocalBackend(DEFAULT_MODEL)
    path = tmp_path / "ep.jsonl"
    run_episode(GridWorld(), backend, seed=3, mode="image", record_path=path, max_ticks=2)
    ticks = read_episode(path).ticks
    first = ticks[0]
    assert first.frame_sha256 and first.usage["output_tokens"] == 0
    assert first.usage["input_tokens"] > 270  # the frame's soft-token run alone is 270
    assert first.timing["encoder_ms"] > 0
    with capsys.disabled():
        print(f"\nimage ticks (usage, timing): {[(t.usage, t.timing) for t in ticks]}")


def test_image_only_session_names_the_run_and_records_meta(tmp_path):
    from gridworld.harness.session import run_session

    backend = LocalBackend(runner=EncodingFake(), calibration=CalibrationConfig())
    result = run_session(
        backend, mode="image", image_only=True, episodes=1, max_ticks=2, out_dir=tmp_path
    )
    assert result.report.meta.image_only and "-image-only-none" in result.report.meta.name
    assert result.report.summary.p50_encoder_ms is not None
    assert cli.main(["play", "--image-only", "--out", str(tmp_path)]) == 2
