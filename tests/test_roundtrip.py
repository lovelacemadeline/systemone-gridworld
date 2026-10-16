"""Story 2.3 — text, image and observation agree (ADR-0001 losslessness)."""

from __future__ import annotations

import random

from decoders import decode_image, decode_text, from_observation

from gridworld.oracle import oracle
from gridworld.render.image import to_image
from gridworld.render.text import to_text
from gridworld.sim import Action, GridWorld, WorldConfig


def episode_observations(seed: int, config: WorldConfig | None = None, noise: float = 0.0):
    """Every observation of one episode, the oracle playing with ``noise`` random actions."""
    rng = random.Random(seed)
    world = GridWorld(config)
    obs = world.reset(seed)
    seen = [obs]
    while True:
        action = rng.choice(list(Action)) if rng.random() < noise else oracle(obs)
        result = world.step(action)
        obs = result.observation
        seen.append(obs)
        if result.done:
            return seen


def assert_lossless(obs):
    truth = from_observation(obs)
    from_text = decode_text(to_text(obs))
    assert from_text == truth
    assert from_text.monster_ids == truth.monster_ids
    assert decode_image(to_image(obs)) == truth


def test_text_image_and_observation_agree_on_100_seeds():
    for seed in range(100):
        obs = episode_observations(seed)[seed % 7]
        assert_lossless(obs)


def test_agree_on_every_state_of_noisy_episodes():
    endings = set()
    for seed in range(30):
        trace = episode_observations(seed, noise=0.3)
        for obs in trace:
            assert_lossless(obs)
        endings.add((trace[-1].player == trace[-1].goal, trace[-1].player_hp == 0))
    assert (True, False) in endings  # a won state, player drawn on the goal


def test_agree_on_other_map_sizes_and_tiles():
    cfg = WorldConfig(width=13, height=7, n_monsters=3, monster_hp=3)
    for seed in range(10):
        for obs in episode_observations(seed, cfg, noise=0.2)[:15]:
            truth = from_observation(obs)
            assert decode_text(to_text(obs)) == truth
            assert decode_image(to_image(obs, tile=24), tile=24) == truth
