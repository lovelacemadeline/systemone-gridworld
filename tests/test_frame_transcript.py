"""Story 4.7 — frame history as a transcript: past frames stay cached."""

from __future__ import annotations

import pytest

from gridworld.backends import build_request
from gridworld.backends.request import IMAGE_KEY
from gridworld.backends.schema import validate_request
from gridworld.harness import Hooks, run_episode
from gridworld.harness.memory import FrameTranscriptMemory, TranscriptMemory, make_memory
from gridworld.harness.session import run_session
from gridworld.sim import Action, GridWorld

pytest.importorskip("mlx_classifiers")
from mlx_classifiers.fitting import CalibrationConfig
from mlx_classifiers.prompt_cache import PromptCacheStore
from test_local_backend import EncodingFake

from gridworld.backends.local import LocalBackend


def play(frames: int, window: bool, ticks: int = 9):
    runner = EncodingFake()
    runner.prompt_cache = PromptCacheStore()
    backend = LocalBackend(runner=runner, calibration=CalibrationConfig())
    logs = []
    memory = make_memory("transcript", mode="image", frames=frames, frame_window=window)
    run_episode(
        GridWorld(),
        backend,
        seed=1,
        mode="image",
        memory=memory,
        max_ticks=ticks,
        hooks=Hooks(after_tick=logs.append),
    )
    return logs


def test_make_memory_picks_the_frame_transcript_in_image_mode():
    assert isinstance(make_memory("transcript", mode="image"), FrameTranscriptMemory)
    assert isinstance(make_memory("transcript"), TranscriptMemory)


def test_state_is_frames_and_answers_then_the_current_frame_and_text():
    world = GridWorld()
    obs = world.reset(1)
    mem = FrameTranscriptMemory(frames=3)
    built = build_request(obs, mode="image")
    after = world.step(Action.WAIT).observation
    mem.observe(obs, built.text, Action.WAIT, after)
    now = build_request(after, mode="image", history=mem.history())
    key, old, answer, new, text = now.request["state"]
    assert key == IMAGE_KEY and answer == "answer: wait" and text == now.text
    assert old == built.request["state"][1]  # the earlier frame block, byte for byte
    assert new["type"] == "image/png" and new != old
    validate_request(now.request)


def test_past_frames_drop_to_half_when_full_and_the_window_slides():
    obs = GridWorld().reset(1)
    for window, want in ((False, [0, 1, 2, 3, 1, 2, 3]), (True, [0, 1, 2, 3, 3, 3, 3])):
        mem, seen = FrameTranscriptMemory(frames=3, window=window), []
        for _ in range(7):
            seen.append(len(mem.history()) // 2)
            mem.observe(obs, "", Action.WAIT, obs)
        assert seen == want
    zero = FrameTranscriptMemory(frames=0)
    zero.observe(obs, "", Action.WAIT, obs)
    assert zero.history() == []


def test_only_the_newest_frame_is_new_on_steady_state_ticks():
    logs = play(frames=3, window=False)
    past = [0, 1, 2, 3, 1, 2, 3, 1, 2]  # past frames each tick saw (drop to frames // 2)
    inp = [t.usage["input_tokens"] for t in logs]
    cached = [t.usage["cached_tokens"] for t in logs]
    steady = [i for i in range(1, len(logs)) if past[i] == past[i - 1] + 1]
    assert steady == [1, 2, 3, 5, 6, 8]
    for i in steady:
        # the previous prompt up to its frame is reused: at least one more frame run cached
        assert cached[i] - cached[i - 1] >= 270
        assert abs(inp[i] - inp[1]) <= 4  # a constant tail: answer, frame, text, question
    assert all(t.timing["encoder_ms"] == 7.0 for t in logs)  # one new image per tick


def test_the_naive_window_misses_every_tick_once_full():
    framed = play(frames=3, window=False)
    window = play(frames=3, window=True)
    full = range(4, 9)
    assert all(window[i].usage["input_tokens"] > 2 * framed[1].usage["input_tokens"] for i in full)
    assert len({window[i].usage["cached_tokens"] for i in full}) == 1  # rules prefix only
    tok = lambda logs: sum(t.usage["input_tokens"] for t in logs)
    assert tok(window) > 1.5 * tok(framed)


def test_frames_flags_reach_the_run_name_and_meta(tmp_path):
    runner = EncodingFake()
    backend = LocalBackend(runner=runner, calibration=CalibrationConfig())
    for window, tag in ((False, "-f2"), (True, "-fwin2")):
        r = run_session(
            backend,
            mode="image",
            memory="transcript",
            frames=2,
            frame_window=window,
            episodes=1,
            max_ticks=3,
            out_dir=tmp_path,
        ).report
        assert r.meta.frames == 2 and r.meta.frame_window is window and tag in r.meta.name
    text = run_session(backend, memory="transcript", episodes=1, max_ticks=1, out_dir=tmp_path)
    assert text.report.meta.frames is None
