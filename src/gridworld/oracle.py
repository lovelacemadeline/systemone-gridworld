"""Scripted oracle (story 1.3): the reference action for any observation.

A pure, deterministic function of the :class:`~gridworld.sim.Observation`, in
priority order:

1. **Fight** when a monster is adjacent and the exchange is winnable: the
   player has more than 1 hp, or the monster ``attack`` would hit
   (:func:`~gridworld.sim.attack_target`) has exactly 1 hp left.
2. **Walk** the first step of the shortest path to the goal that avoids
   monster cells and every cell adjacent to a monster, if such a path exists;
   otherwise the first step of the shortest path that avoids only walls and
   monster cells (both via :func:`~gridworld.sim.bfs_path`).
3. **Wait** when the goal is unreachable.
"""

from __future__ import annotations

from collections.abc import Callable

from .sim import MOVES, Action, GridWorld, Observation, StepResult, attack_target, bfs_path

__all__ = ["oracle", "play_episode"]

_STEP_TO_ACTION = {delta: action for action, delta in MOVES.items()}


def oracle(obs: Observation) -> Action:
    """The reference action for ``obs`` (see the module docstring for the rule)."""
    target = attack_target(obs)
    if target is not None and (obs.player_hp > 1 or target.hp == 1):
        return Action.ATTACK
    monster_cells = {m.pos for m in obs.monsters}
    danger = {(m.pos[0] + dx, m.pos[1] + dy) for m in obs.monsters for dx, dy in MOVES.values()}
    for blocked in (obs.walls | monster_cells | danger, obs.walls | monster_cells):
        path = bfs_path(obs.player, obs.goal, blocked, obs.width, obs.height)
        if path is not None and len(path) > 1:
            (x0, y0), (x1, y1) = path[0], path[1]
            return _STEP_TO_ACTION[(x1 - x0, y1 - y0)]
    return Action.WAIT


def play_episode(
    world: GridWorld, seed: int, policy: Callable[[Observation], Action] = oracle
) -> tuple[list[Action], StepResult]:
    """Run ``policy`` from ``world.reset(seed)`` to the end; return its actions and last step."""
    obs = world.reset(seed)
    actions: list[Action] = []
    while True:
        action = policy(obs)
        actions.append(action)
        result = world.step(action)
        obs = result.observation
        if result.done:
            return actions, result
