"""Story 1.1 — the observation record and seeded map generation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from gridworld.sim import (
    Action,
    Observation,
    WorldConfig,
    bfs_path,
    generate_map,
    manhattan,
)

SEEDS = range(200)


def test_action_order_is_the_wire_option_order():
    assert [a.value for a in Action] == ["north", "south", "east", "west", "attack", "wait"]


def test_generate_map_is_deterministic():
    for seed in SEEDS:
        assert generate_map(seed) == generate_map(seed)
    assert generate_map(1) != generate_map(2)


def test_generated_map_has_a_path_from_player_to_goal():
    for seed in SEEDS:
        obs = generate_map(seed)
        assert bfs_path(obs.player, obs.goal, obs.walls, obs.width, obs.height), seed


def test_generated_map_invariants():
    cfg = WorldConfig()
    for seed in SEEDS:
        obs = generate_map(seed, cfg)
        path = bfs_path(obs.player, obs.goal, obs.walls, obs.width, obs.height)
        cells = [obs.player, obs.goal, *(m.pos for m in obs.monsters)]
        assert len(set(cells)) == len(cells)
        assert not set(cells) & obs.walls
        assert len(obs.monsters) == cfg.n_monsters
        assert [m.id for m in obs.monsters] == list(range(cfg.n_monsters))
        for m in obs.monsters:
            assert m.pos not in path
            assert manhattan(m.pos, obs.player) > cfg.sight_radius
        assert (obs.tick, obs.last_action, obs.player_hp) == (0, None, cfg.player_hp)


def test_config_controls_size_density_and_monsters():
    cfg = WorldConfig(width=14, height=8, wall_density=0.0, n_monsters=3)
    obs = generate_map(3, cfg)
    assert (obs.width, obs.height, len(obs.monsters)) == (14, 8, 3)
    assert obs.walls == frozenset()


def test_observation_json_round_trip():
    for seed in range(20):
        obs = generate_map(seed)
        assert Observation.model_validate_json(obs.model_dump_json()) == obs


def test_observation_json_is_canonical():
    obs = generate_map(5)
    walls = obs.model_dump(mode="json")["walls"]
    assert walls == sorted(walls)


def test_observation_is_hashable_and_frozen():
    obs = generate_map(0)
    assert hash(obs) == hash(generate_map(0))
    assert len({obs, generate_map(0)}) == 1
    with pytest.raises(ValidationError):
        obs.tick = 3  # type: ignore[misc]
