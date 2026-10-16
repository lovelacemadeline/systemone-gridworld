"""Story 1.3 — the scripted oracle policy."""

from __future__ import annotations

from gridworld.oracle import oracle, play_episode
from gridworld.sim import Action, GridWorld, generate_map


def test_oracle_completes_95_percent_of_200_seeds():
    world = GridWorld()
    failures = {}
    for seed in range(200):
        actions, last = play_episode(world, seed)
        if last.info["reason"] != "goal":
            failures[seed] = (last.info["reason"], len(actions))
    rate = 1 - len(failures) / 200
    print(f"oracle completion {rate:.1%}; failing seeds: {failures}")
    assert rate >= 0.95, f"completion {rate:.1%}; failing seeds: {failures}"


def test_oracle_is_deterministic():
    world = GridWorld()
    for seed in range(20):
        obs = generate_map(seed)
        assert oracle(obs) == oracle(obs)
        assert play_episode(world, seed)[0] == play_episode(world, seed)[0]


def test_oracle_attacks_when_the_exchange_is_winnable(make_obs):
    assert oracle(make_obs(player=(2, 2), monsters=[((2, 1), 2)])) is Action.ATTACK
    assert oracle(make_obs(player=(2, 2), player_hp=1, monsters=[((2, 1), 1)])) is Action.ATTACK


def test_oracle_does_not_attack_a_losing_exchange(make_obs):
    obs = make_obs(player=(2, 2), goal=(4, 4), player_hp=1, monsters=[((2, 1), 2)])
    assert oracle(obs) is not Action.ATTACK


def test_oracle_takes_the_shortest_path(make_obs):
    assert oracle(make_obs(player=(0, 0), goal=(0, 4))) is Action.SOUTH
    assert oracle(make_obs(player=(0, 0), goal=(4, 0))) is Action.EAST


def test_oracle_routes_around_monster_adjacent_cells(make_obs):
    # Straight south enters (3, 2), next to the monster at (4, 2); the detour via x=2 does not.
    obs = make_obs(player=(3, 1), goal=(3, 4), monsters=[((4, 2), 2)])
    assert oracle(obs) is Action.WEST


def test_oracle_falls_back_to_plain_path_when_no_safe_one(make_obs):
    # A corridor: the only route passes next to the monster.
    walls = [(x, y) for x in range(5) for y in (0, 2)]
    obs = make_obs(player=(0, 1), goal=(4, 1), walls=walls, monsters=[((2, 3), 2)])
    assert oracle(obs) is Action.EAST


def test_oracle_waits_when_goal_is_unreachable(make_obs):
    obs = make_obs(player=(0, 0), goal=(4, 4), walls=[(1, 0), (0, 1)])
    assert oracle(obs) is Action.WAIT
