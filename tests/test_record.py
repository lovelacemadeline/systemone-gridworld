"""Story 1.4 — JSONL episode recording and replay."""

from __future__ import annotations

import json

import pytest

from gridworld.oracle import oracle
from gridworld.record import (
    EpisodeHeader,
    EpisodeRecorder,
    ReplayMismatch,
    read_episode,
    replay,
)
from gridworld.sim import Action, GridWorld, WorldConfig


def record_oracle_episode(path, seed, config=None, *, end=True):
    """Play the oracle and record it; return the observations it saw plus the terminal one."""
    world = GridWorld(config)
    obs = world.reset(seed)
    seen = [obs]
    header = EpisodeHeader(seed=seed, config=world.config, backend="oracle", mode="text")
    with EpisodeRecorder(path, header) as rec:
        while True:
            action = oracle(obs)
            probs = {a: (0.9 if a is action else 0.02) for a in Action}
            rec.tick(obs, action, oracle_action=action, probabilities=probs, timing={"step": 0.1})
            result = world.step(action)
            obs = result.observation
            seen.append(obs)
            if result.done:
                break
        if end:
            rec.end(obs, result.reward, result.info["reason"])
    return seen


def test_recorded_episode_replays(tmp_path):
    for seed in range(10):
        path = tmp_path / f"ep{seed}.jsonl"
        seen = record_oracle_episode(path, seed)
        assert list(replay(path)) == seen


def test_file_is_header_then_ticks_then_end(tmp_path):
    path = tmp_path / "ep.jsonl"
    seen = record_oracle_episode(path, 3)
    kinds = [json.loads(line)["kind"] for line in path.read_text().splitlines()]
    assert kinds == ["header"] + ["tick"] * (len(seen) - 1) + ["end"]


def test_read_episode_round_trips_fields_without_the_sim(tmp_path):
    path = tmp_path / "ep.jsonl"
    cfg = WorldConfig(width=8, height=6, n_monsters=1)
    seen = record_oracle_episode(path, 11, cfg)
    ep = read_episode(path)
    assert ep.header.config == cfg and ep.header.seed == 11
    assert [t.observation for t in ep.ticks] == seen[:-1]
    assert ep.end is not None and ep.end.observation == seen[-1]
    first = ep.ticks[0]
    assert first.oracle_action is first.action
    assert first.probabilities[first.action] == 0.9
    assert first.timing == {"step": 0.1}


def test_replay_without_end_line_yields_the_decision_observations(tmp_path):
    path = tmp_path / "ep.jsonl"
    seen = record_oracle_episode(path, 4, end=False)
    assert read_episode(path).end is None
    assert list(replay(path)) == seen[:-1]


def test_nullable_probabilities_and_timing(tmp_path):
    path = tmp_path / "ep.jsonl"
    world = GridWorld()
    obs = world.reset(0)
    header = EpisodeHeader(seed=0, config=world.config, backend="none", mode="text")
    with EpisodeRecorder(path, header) as rec:
        rec.tick(obs, Action.WAIT, oracle_action=oracle(obs))
    tick = read_episode(path).ticks[0]
    assert tick.probabilities is None and tick.timing is None


def test_replay_detects_a_tampered_observation(tmp_path):
    path = tmp_path / "ep.jsonl"
    record_oracle_episode(path, 2)
    lines = path.read_text().splitlines()
    rec = json.loads(lines[3])
    rec["observation"]["player_hp"] -= 1
    lines[3] = json.dumps(rec)
    path.write_text("\n".join(lines) + "\n")
    with pytest.raises(ReplayMismatch, match="tick 2"):
        list(replay(path))


def test_replay_detects_a_changed_action(tmp_path):
    path = tmp_path / "ep.jsonl"
    record_oracle_episode(path, 2)
    lines = path.read_text().splitlines()
    rec = json.loads(lines[1])
    rec["action"] = "attack" if rec["action"] != "attack" else "wait"
    lines[1] = json.dumps(rec)
    path.write_text("\n".join(lines) + "\n")
    with pytest.raises(ReplayMismatch):
        list(replay(path))


def test_read_episode_rejects_a_file_without_header(tmp_path):
    path = tmp_path / "ep.jsonl"
    record_oracle_episode(path, 1)
    path.write_text("\n".join(path.read_text().splitlines()[1:]) + "\n")
    with pytest.raises(ValueError, match="header"):
        read_episode(path)


def test_git_rev_is_short_hash_or_none(tmp_path):
    from gridworld.record import git_rev

    assert git_rev(tmp_path) is None
    rev = git_rev()
    assert rev is None or (rev.isalnum() and len(rev) >= 7)
