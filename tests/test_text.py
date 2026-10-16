"""Story 2.1 — text renderer with stable-first layout."""

from __future__ import annotations

from gridworld.render.text import LEGEND, compass, to_text
from gridworld.sim import Action, GridWorld, generate_map


def test_layout_is_legend_then_map_then_one_status_line():
    obs = generate_map(3)
    lines = to_text(obs).split("\n")
    legend = LEGEND.split("\n")
    assert lines[: len(legend)] == legend
    assert lines[len(legend)].startswith("Map 10x10")
    map_rows = lines[len(legend) + 2 : -1]
    assert len(map_rows) == obs.height
    assert {len(r) for r in map_rows} == {len(lines[len(legend) + 1])}
    assert lines[-1].startswith("Status: ") and sum(ln.startswith("Status") for ln in lines) == 1


def test_glyphs_and_coordinates(make_obs):
    obs = make_obs(player=(1, 0), goal=(4, 4), walls=[(0, 0)], monsters=[((3, 2), 2)])
    rows = to_text(obs).split("\n")[5:-1]
    assert rows == ["0 #@...", "1 .....", "2 ...M.", "3 .....", "4 ....G"]


def test_moving_changes_only_the_two_cells_and_the_status_line(make_obs):
    a = make_obs(player=(2, 2), goal=(4, 4), walls=[(0, 1)], monsters=[((0, 4), 2)])
    b = a.model_copy(update={"player": (3, 2)})
    ta, tb = to_text(a).split("\n"), to_text(b).split("\n")
    changed = [i for i, (la, lb) in enumerate(zip(ta, tb, strict=True)) if la != lb]
    row = 5 + 2  # legend (3) + "Map" line + column header, then y = 2
    assert set(changed) <= {row, len(ta) - 1}  # that map row and the status line only
    diff = [j for j, (ca, cb) in enumerate(zip(ta[row], tb[row], strict=True)) if ca != cb]
    assert len(diff) == 2


def test_consecutive_ticks_share_prefix_up_to_the_first_moved_cell():
    world = GridWorld()
    obs = world.reset(3)
    nxt = world.step(Action.NORTH).observation
    ta, tb = to_text(obs), to_text(nxt)
    common = next(i for i, (x, y) in enumerate(zip(ta, tb, strict=False)) if x != y)
    assert common >= len(LEGEND)
    assert ta.rsplit("\n", 1)[0][:common] == tb[:common]


def test_status_line_reports_threats_goal_and_last_action(make_obs):
    obs = make_obs(player=(2, 2), goal=(0, 4), monsters=[((2, 1), 2), ((3, 2), 1)])
    obs = obs.model_copy(update={"last_action": Action.WEST, "tick": 9, "player_hp": 4})
    status = to_text(obs).split("\n")[-1]
    assert status == (
        "Status: hp 4 | tick 9 | last west | adjacent M: north, east | goal: south-west"
        " | monsters: M0 (2,1) hp 2, M1 (3,2) hp 1"
    )


def test_compass():
    assert compass((2, 2), (2, 0)) == "north"
    assert compass((2, 2), (5, 5)) == "south-east"
    assert compass((2, 2), (2, 2)) == "here"


def test_player_on_goal_says_here(make_obs):
    obs = make_obs(player=(4, 4), goal=(4, 4))
    text = to_text(obs)
    assert "G" not in text.split("\n")[-2] and "goal: here" in text
