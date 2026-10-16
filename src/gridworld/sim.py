"""The simulator (stories 1.1, 1.2): one structured observation, a seeded map, step dynamics.

Coordinates are ``(x, y)`` cells with ``(0, 0)`` top-left; ``x`` grows east,
``y`` grows south. Everything is reproducible from ``(config, seed, actions)``:
the only randomness is a :class:`random.Random` seeded once in
:func:`generate_map`, and :meth:`GridWorld.step` is a pure function of the
current observation and the action.

The :class:`Observation` is the single source every renderer derives from
(ADR-0001). It is frozen, hashable, and JSON round-trips to an equal value.
Invariants a renderer may rely on: the player, the goal, walls and monsters
occupy pairwise distinct cells, except that the player may stand on the goal
in the terminal observation of a won episode. Monsters never enter the goal.

One tick of :meth:`GridWorld.step`, in order:

1. **Player.** A move into a wall, an edge or a monster is a no-op. ``attack``
   deals 1 damage to :func:`attack_target` (no-op when nothing is adjacent);
   a monster at 0 hp is removed. ``wait`` does nothing.
2. **Goal.** If the player now stands on the goal the episode ends (+1) and
   monsters do not act.
3. **Monsters**, in id order: one within Manhattan ``sight_radius`` and not
   already adjacent steps one cell toward the player along the axis with the
   larger gap (tie: ``x`` first), falling back to the other axis when blocked
   by a wall, a monster, the player or the goal; otherwise it stays.
4. **Damage.** Every monster adjacent to the player deals 1; at 0 hp the
   episode ends (-1).
5. **Clock.** ``tick`` advances on every step; reaching ``tick_limit`` without
   another ending ends the episode with reward 0.
"""

from __future__ import annotations

import random
from collections import deque
from collections.abc import Iterable
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer

__all__ = [
    "Action",
    "Cell",
    "GridWorld",
    "Monster",
    "Observation",
    "StepResult",
    "WorldConfig",
    "adjacent",
    "attack_target",
    "bfs_path",
    "generate_map",
    "legal_actions",
    "manhattan",
    "neighbors",
]

Cell = tuple[int, int]


class Action(StrEnum):
    """The six options every backend chooses between, in wire order."""

    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"
    ATTACK = "attack"
    WAIT = "wait"


MOVES: dict[Action, Cell] = {
    Action.NORTH: (0, -1),
    Action.SOUTH: (0, 1),
    Action.EAST: (1, 0),
    Action.WEST: (-1, 0),
}


class Monster(BaseModel):
    """One monster: a stable ``id`` (spawn order), its cell and remaining hp."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: int
    pos: Cell
    hp: int = Field(ge=1)


class Observation(BaseModel):
    """Everything there is to know about one game state (ADR-0001).

    ``monsters`` is sorted by ``id``; ``walls`` serialises as a sorted list so
    the JSON form is canonical. ``items`` is reserved for later item kinds and
    is always empty in v1. ``last_action`` is ``None`` only right after reset.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    width: int = Field(ge=2)
    height: int = Field(ge=2)
    walls: frozenset[Cell]
    player: Cell
    goal: Cell
    monsters: tuple[Monster, ...] = ()
    items: tuple[Cell, ...] = ()
    player_hp: int = Field(ge=0)
    tick: int = Field(default=0, ge=0)
    last_action: Action | None = None
    seed: int

    @field_serializer("walls")
    def _sorted_walls(self, walls: frozenset[Cell]) -> list[Cell]:
        return sorted(walls)

    def in_bounds(self, cell: Cell) -> bool:
        x, y = cell
        return 0 <= x < self.width and 0 <= y < self.height

    def monster_at(self, cell: Cell) -> Monster | None:
        return next((m for m in self.monsters if m.pos == cell), None)


class WorldConfig(BaseModel):
    """Map and rule parameters. With a seed, this fully determines an episode's start."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    width: int = Field(default=10, ge=4)
    height: int = Field(default=10, ge=4)
    wall_density: float = Field(default=0.2, ge=0.0, lt=0.6)
    n_monsters: int = Field(default=2, ge=0)
    player_hp: int = Field(default=6, ge=1)
    monster_hp: int = Field(default=2, ge=1)
    sight_radius: int = Field(default=4, ge=0)
    tick_limit: int = Field(default=200, ge=1)


class StepResult(BaseModel):
    """What :meth:`GridWorld.step` returns.

    ``info`` keys: ``reason`` (``"goal"``, ``"dead"``, ``"timeout"`` or ``None``),
    ``moved`` (bool), ``killed`` (monster id or ``None``), ``damage_taken`` (int).
    """

    model_config = ConfigDict(frozen=True)

    observation: Observation
    reward: int
    done: bool
    info: dict[str, Any]


def manhattan(a: Cell, b: Cell) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def adjacent(a: Cell, b: Cell) -> bool:
    """True when ``a`` and ``b`` share an edge (diagonals do not count)."""
    return manhattan(a, b) == 1


def neighbors(cell: Cell, width: int, height: int) -> list[Cell]:
    """In-bounds edge neighbours in the fixed order north, south, east, west."""
    x, y = cell
    out = []
    for dx, dy in MOVES.values():
        nx, ny = x + dx, y + dy
        if 0 <= nx < width and 0 <= ny < height:
            out.append((nx, ny))
    return out


def bfs_path(
    start: Cell, goal: Cell, blocked: Iterable[Cell], width: int, height: int
) -> list[Cell] | None:
    """Shortest path ``[start, ..., goal]`` avoiding ``blocked``, or ``None``.

    Deterministic: neighbours expand in :func:`neighbors` order, so among equal
    length paths the one preferring north, south, east, west wins. ``goal`` is
    reachable even if listed in ``blocked``; ``start`` is never checked.
    """
    blocked = set(blocked) - {goal}
    prev: dict[Cell, Cell | None] = {start: None}
    queue = deque([start])
    while queue:
        cur = queue.popleft()
        if cur == goal:
            path = [cur]
            while (p := prev[path[-1]]) is not None:
                path.append(p)
            return path[::-1]
        for nxt in neighbors(cur, width, height):
            if nxt not in prev and nxt not in blocked:
                prev[nxt] = cur
                queue.append(nxt)
    return None


def attack_target(obs: Observation) -> Monster | None:
    """The monster ``attack`` hits: the adjacent one with least hp, then lowest id."""
    near = [m for m in obs.monsters if adjacent(m.pos, obs.player)]
    return min(near, key=lambda m: (m.hp, m.id), default=None)


def legal_actions(obs: Observation) -> tuple[Action, ...]:
    """The actions that do something from ``obs``, in :class:`Action` order.

    A move is legal when its target is in bounds, not a wall and not a monster
    (each of those makes :meth:`GridWorld.step` a no-op); ``attack`` when a
    monster is edge-adjacent (:func:`attack_target`); ``wait`` always. Shares the
    movement rules with ``step`` so the two cannot drift (story 4.5).
    """
    monsters = {m.pos for m in obs.monsters}
    out = []
    for action, (dx, dy) in MOVES.items():
        target = (obs.player[0] + dx, obs.player[1] + dy)
        if obs.in_bounds(target) and target not in obs.walls and target not in monsters:
            out.append(action)
    if attack_target(obs) is not None:
        out.append(Action.ATTACK)
    out.append(Action.WAIT)
    return tuple(out)


def generate_map(seed: int, config: WorldConfig | None = None) -> Observation:
    """The tick-0 observation for ``seed``: same seed and config, equal observation.

    Walls are sampled at ``wall_density``; player and goal go on free cells at
    least ``(width + height) // 2`` apart; the draw is retried (from the same
    generator, so still deterministic) until BFS finds a player-to-goal path.
    Monsters spawn on free cells off that shortest path, never on the goal, and
    farther than ``sight_radius`` from the player, so no monster is awake at
    tick 0.
    """
    cfg = config or WorldConfig()
    rng = random.Random(seed)
    cells = [(x, y) for y in range(cfg.height) for x in range(cfg.width)]
    min_gap = (cfg.width + cfg.height) // 2
    for _ in range(1000):
        walls = frozenset(c for c in cells if rng.random() < cfg.wall_density)
        free = [c for c in cells if c not in walls]
        if len(free) < 2 + cfg.n_monsters:
            continue
        player, goal = rng.sample(free, 2)
        if manhattan(player, goal) < min_gap:
            continue
        path = bfs_path(player, goal, walls, cfg.width, cfg.height)
        if path is None:
            continue
        spawn = [c for c in free if c not in path and manhattan(c, player) > cfg.sight_radius]
        if len(spawn) < cfg.n_monsters:
            continue
        monsters = tuple(
            Monster(id=i, pos=pos, hp=cfg.monster_hp)
            for i, pos in enumerate(rng.sample(spawn, cfg.n_monsters))
        )
        return Observation(
            width=cfg.width,
            height=cfg.height,
            walls=walls,
            player=player,
            goal=goal,
            monsters=monsters,
            player_hp=cfg.player_hp,
            seed=seed,
        )
    raise ValueError(f"no solvable map for seed {seed} with {cfg!r}")


def _sign(v: int) -> int:
    return (v > 0) - (v < 0)


class GridWorld:
    """A seeded episode: :meth:`reset`, then :meth:`step` until ``done``."""

    def __init__(self, config: WorldConfig | None = None) -> None:
        self.config = config or WorldConfig()
        self._obs: Observation | None = None
        self.done = False

    def reset(self, seed: int) -> Observation:
        """Start a new episode from :func:`generate_map` and return its first observation."""
        self._obs = generate_map(seed, self.config)
        self.done = False
        return self._obs

    def load(self, observation: Observation) -> Observation:
        """Continue from an arbitrary observation (hand-built test states, resumed replays)."""
        self._obs = observation
        self.done = False
        return observation

    def observe(self) -> Observation:
        """The current observation (no side effects)."""
        if self._obs is None:
            raise RuntimeError("call reset(seed) before observe()")
        return self._obs

    def step(self, action: Action | str) -> StepResult:
        """Advance one tick (see the module docstring for the exact order)."""
        obs = self.observe()
        if self.done:
            raise RuntimeError("episode is done; call reset(seed)")
        action = Action(action)
        cfg = self.config
        player = obs.player
        monsters = {m.id: m for m in obs.monsters}
        moved, killed = False, None

        if action in MOVES:
            dx, dy = MOVES[action]
            target = (player[0] + dx, player[1] + dy)
            occupied = {m.pos for m in monsters.values()}
            if obs.in_bounds(target) and target not in obs.walls and target not in occupied:
                player, moved = target, True
        elif action is Action.ATTACK and (hit := attack_target(obs)) is not None:
            if hit.hp <= 1:
                del monsters[hit.id]
                killed = hit.id
            else:
                monsters[hit.id] = hit.model_copy(update={"hp": hit.hp - 1})

        reward, reason, damage, hp = 0, None, 0, obs.player_hp
        if player == obs.goal:
            reward, reason = 1, "goal"
        else:
            for mid in sorted(monsters):
                m = monsters[mid]
                new = self._monster_step(m.pos, player, obs, monsters)
                if new != m.pos:
                    monsters[mid] = m.model_copy(update={"pos": new})
            damage = sum(adjacent(m.pos, player) for m in monsters.values())
            hp = max(0, hp - damage)
            if hp == 0:
                reward, reason = -1, "dead"

        tick = obs.tick + 1
        if reason is None and tick >= cfg.tick_limit:
            reason = "timeout"
        self._obs = obs.model_copy(
            update={
                "player": player,
                "monsters": tuple(monsters[i] for i in sorted(monsters)),
                "player_hp": hp,
                "tick": tick,
                "last_action": action,
            }
        )
        self.done = reason is not None
        info = {"reason": reason, "moved": moved, "killed": killed, "damage_taken": damage}
        return StepResult(observation=self._obs, reward=reward, done=self.done, info=info)

    def _monster_step(
        self, pos: Cell, player: Cell, obs: Observation, monsters: dict[int, Monster]
    ) -> Cell:
        dist = manhattan(pos, player)
        if dist > self.config.sight_radius or dist <= 1:
            return pos
        gx, gy = player[0] - pos[0], player[1] - pos[1]
        steps = [(_sign(gx), 0), (0, _sign(gy))]
        if abs(gy) > abs(gx):
            steps.reverse()
        occupied = {m.pos for m in monsters.values()} | {player, obs.goal}
        for dx, dy in steps:
            if (dx, dy) == (0, 0):
                continue
            cand = (pos[0] + dx, pos[1] + dy)
            if obs.in_bounds(cand) and cand not in obs.walls and cand not in occupied:
                return cand
        return pos
