"""Story 1.2 — step dynamics: movement, monsters, combat, termination."""

from __future__ import annotations

import random

import pytest

from gridworld.sim import Action, GridWorld, WorldConfig


def start(obs, **cfg) -> GridWorld:
    w = GridWorld(WorldConfig(**cfg))
    w.load(obs)
    return w


def test_move_into_wall_is_noop_and_ticks(make_obs):
    w = start(make_obs(player=(2, 2), walls=[(2, 1)]))
    r = w.step(Action.NORTH)
    assert r.observation.player == (2, 2)
    assert r.observation.tick == 1
    assert r.observation.last_action is Action.NORTH
    assert r.info["moved"] is False and not r.done


def test_move_into_edge_is_noop(make_obs):
    w = start(make_obs(player=(0, 0)))
    assert w.step(Action.WEST).observation.player == (0, 0)
    assert w.step(Action.NORTH).observation.player == (0, 0)


def test_move_into_monster_is_noop(make_obs):
    w = start(make_obs(player=(2, 2), monsters=[((3, 2), 2)]))
    assert w.step(Action.EAST).observation.player == (2, 2)


def test_move_succeeds_on_open_cell(make_obs):
    w = start(make_obs(player=(2, 2)))
    r = w.step(Action.SOUTH)
    assert r.observation.player == (2, 3) and r.info["moved"] is True


def test_attack_removes_adjacent_monster_with_hp_1(make_obs):
    w = start(make_obs(player=(2, 2), monsters=[((2, 1), 1)]))
    r = w.step(Action.ATTACK)
    assert r.observation.monsters == ()
    assert r.info["killed"] == 0
    assert r.observation.player_hp == 6


def test_attack_hits_lowest_hp_then_lowest_id(make_obs):
    w = start(make_obs(player=(2, 2), monsters=[((2, 1), 2), ((1, 2), 2), ((3, 2), 1)]))
    r = w.step(Action.ATTACK)
    assert [m.id for m in r.observation.monsters] == [0, 1]
    r = w.step(Action.ATTACK)
    assert [(m.id, m.hp) for m in r.observation.monsters] == [(0, 1), (1, 2)]


def test_attack_with_nothing_adjacent_is_noop(make_obs):
    w = start(make_obs(player=(2, 2), monsters=[((4, 0), 2)]))
    r = w.step(Action.ATTACK)
    assert r.observation.monsters[0].hp == 2


def test_monster_steps_toward_player_x_first_on_tie(make_obs):
    w = start(make_obs(player=(0, 0), goal=(4, 0), monsters=[((2, 2), 2)]))
    assert w.step(Action.WAIT).observation.monsters[0].pos == (1, 2)


def test_monster_steps_along_the_larger_gap(make_obs):
    w = start(make_obs(player=(0, 0), goal=(4, 0), monsters=[((1, 3), 2)]))
    assert w.step(Action.WAIT).observation.monsters[0].pos == (1, 2)


def test_blocked_monster_falls_back_to_other_axis(make_obs):
    w = start(make_obs(player=(0, 0), goal=(4, 0), walls=[(1, 2)], monsters=[((2, 2), 2)]))
    assert w.step(Action.WAIT).observation.monsters[0].pos == (2, 1)


def test_monster_beyond_sight_radius_stays(make_obs):
    w = start(make_obs(player=(0, 0), goal=(0, 4), monsters=[((4, 4), 2)]), sight_radius=4)
    assert w.step(Action.WAIT).observation.monsters[0].pos == (4, 4)


def test_monsters_never_enter_the_goal(make_obs):
    w = start(make_obs(player=(0, 0), goal=(1, 2), monsters=[((2, 2), 2)]))
    assert w.step(Action.WAIT).observation.monsters[0].pos == (2, 1)


def test_adjacent_monster_deals_damage_at_end_of_tick(make_obs):
    w = start(make_obs(player=(2, 2), monsters=[((2, 1), 2), ((1, 2), 2)]))
    r = w.step(Action.WAIT)
    assert r.observation.player_hp == 4 and r.info["damage_taken"] == 2


def test_hp_zero_ends_with_minus_one(make_obs):
    w = start(make_obs(player=(2, 2), player_hp=1, monsters=[((2, 1), 2)]))
    r = w.step(Action.WAIT)
    assert (r.done, r.reward, r.info["reason"], r.observation.player_hp) == (True, -1, "dead", 0)


def test_goal_ends_with_plus_one_before_monsters_act(make_obs):
    w = start(make_obs(player=(3, 4), goal=(4, 4), player_hp=1, monsters=[((4, 2), 2)]))
    r = w.step(Action.EAST)
    assert (r.done, r.reward, r.info["reason"]) == (True, 1, "goal")
    assert r.observation.player_hp == 1 and r.observation.monsters[0].pos == (4, 2)


def test_tick_limit_ends_with_zero(make_obs):
    w = start(make_obs(), tick_limit=3)
    results = [w.step(Action.WAIT) for _ in range(3)]
    assert [r.done for r in results] == [False, False, True]
    assert (results[-1].reward, results[-1].info["reason"]) == (0, "timeout")


def test_step_after_done_raises(make_obs):
    w = start(make_obs(), tick_limit=1)
    w.step(Action.WAIT)
    with pytest.raises(RuntimeError):
        w.step(Action.WAIT)


def test_step_accepts_action_strings(world):
    assert world.step("wait").observation.last_action is Action.WAIT


def test_same_seed_and_actions_replay_identically():
    rng = random.Random(0)
    for seed in range(30):
        actions = [rng.choice(list(Action)) for _ in range(60)]
        finals = []
        for _ in range(2):
            w = GridWorld()
            w.reset(seed)
            trace = []
            for a in actions:
                r = w.step(a)
                trace.append(r.observation)
                if r.done:
                    break
            finals.append(trace)
        assert finals[0] == finals[1]
