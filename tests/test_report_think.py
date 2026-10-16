"""Story 5.4 — the report across think triggers: quality versus cost."""

from __future__ import annotations

from pathlib import Path

from gridworld import cli
from gridworld.backends.fake import FakeBackend
from gridworld.harness.plan import FakePlanner
from gridworld.harness.report import RunReport, comparison_table
from gridworld.harness.session import run_session
from gridworld.harness.think import ThinkConfig


def session(tmp_path, think: ThinkConfig | None, planner=None, noul=0.1):
    return run_session(
        FakeBackend(noul=noul),
        memory="summary",
        episodes=3,
        out_dir=tmp_path,
        think=think,
        planner=planner,
    )


def test_plan_counts_tokens_time_and_pause_distribution(tmp_path):
    planner = FakePlanner(tokens=50, latency_s=0.01)
    r = session(tmp_path, ThinkConfig(trigger="demand", cooldown=4), planner, noul=0.9)
    s = r.report.summary
    assert s.plans == len(planner.calls) > 3 and s.plans_per_episode == s.plans / 3
    assert s.plan_tokens_per_plan == 50 and s.plans_truncated == 0
    assert s.planning_s >= 0.01 * s.plans and 0 < s.planning_share < 1
    assert s.pause_p_mean == 0.9 and s.pause_p_hist[9] == s.ticks
    assert s.tokens_per_episode > 0
    assert r.report.meta.think["trigger"] == "demand"
    assert "-think-demand-direct" in r.report.meta.name


def test_never_has_no_plans_and_start_has_one_per_episode(tmp_path):
    never = session(tmp_path / "a", None).report.summary
    start = session(tmp_path / "b", ThinkConfig(trigger="start"), FakePlanner()).report.summary
    assert never.plans == 0 and never.pause_p_mean is None and never.plans_per_episode == 0
    assert start.plans == 3 and start.pause_p_mean is None


def test_one_table_across_triggers(tmp_path, capsys):
    reports = [
        session(tmp_path / "a", None).report,
        session(tmp_path / "b", ThinkConfig(trigger="start"), FakePlanner()).report,
        session(tmp_path / "c", ThinkConfig(trigger="demand"), FakePlanner(), noul=0.9).report,
    ]
    table = comparison_table(reports).split("\n")
    assert len(table) == 2 + 3
    assert "completion" in table[0] and "plans/ep" in table[0] and "tokens/ep" in table[0]
    assert "think never" in table[2] and "think start/direct/free" in table[3]
    assert "think demand/direct/free" in table[4]
    paths = [str(next((tmp_path / d).glob("*.json"))) for d in "abc"]
    assert cli.main(["compare", *paths]) == 0
    assert capsys.readouterr().out.strip().split("\n")[2:] == table[2:]
    assert RunReport.model_validate_json(Path(paths[2]).read_text()).summary.plans > 0
