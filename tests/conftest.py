"""Shared fixtures: a seeded world and a factory for hand-built observations."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from gridworld.sim import GridWorld, Monster, Observation

SEED = 7


@pytest.fixture
def world() -> GridWorld:
    """A default-config world already reset to ``SEED``."""
    w = GridWorld()
    w.reset(SEED)
    return w


@pytest.fixture
def make_obs() -> Callable[..., Observation]:
    """Build a small open-map observation; ``monsters`` is a list of ``(pos, hp)``."""

    def build(
        *,
        player=(2, 2),
        goal=(4, 4),
        walls=(),
        monsters=(),
        player_hp=6,
        width=5,
        height=5,
    ) -> Observation:
        return Observation(
            width=width,
            height=height,
            walls=frozenset(walls),
            player=player,
            goal=goal,
            monsters=tuple(Monster(id=i, pos=p, hp=hp) for i, (p, hp) in enumerate(monsters)),
            player_hp=player_hp,
            seed=0,
        )

    return build
