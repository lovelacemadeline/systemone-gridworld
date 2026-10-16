"""The run report (story 4.2): ``runs/<name>.md`` and ``runs/<name>.json``.

``<name>`` is ``<UTC stamp>-<backend>-<mode>-<memory>`` (backend id slugified);
the episode files of the run live in ``runs/<name>/``. The JSON is the full
:class:`RunReport` (provenance, aggregate, every episode summary); the
markdown is the human view: provenance, a headline table, and one row per
episode.

Provenance: backend id, model id when the backend exposes ``model_id``, mode,
memory, git rev, power state (:func:`~gridworld.harness.provenance.power_state`),
world config, prefix length and sha256 (and, story 4.8, every hot-reloaded
prefix version), seeds, and whether the run was
interrupted.
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from ..sim import WorldConfig
from .score import EpisodeSummary, RunSummary, summarize_run

__all__ = [
    "RunMeta",
    "RunReport",
    "build_report",
    "comparison_table",
    "run_name",
    "to_markdown",
    "write_report",
]


class RunMeta(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    backend: str
    model: str | None
    mode: str
    memory: str
    legal_only: bool = False
    labels: str = "letters"
    #: System Two settings (trigger, style, max_tokens, ...) or None when not thinking.
    think: dict[str, Any] | None = None
    #: The planner's id and model when System Two is on (story 5.5: may differ from ``model``).
    planner: str | None = None
    planner_model: str | None = None
    #: Summary-memory knobs (story 4.6).
    memory_k: int = 3
    memory_visits: bool = False
    git_rev: str | None
    power: dict[str, Any]
    config: WorldConfig
    prefix_chars: int
    prefix_sha256: str
    #: Story 4.8: every rules-prefix version the run used (version, sha256, chars, source).
    prefix_versions: list[dict[str, Any]] = []
    started: str
    finished: str | None = None
    interrupted: bool = False


class RunReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    meta: RunMeta
    summary: RunSummary
    episodes: list[EpisodeSummary]


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9.]+", "-", text).strip("-").lower()


def run_name(
    backend: str,
    mode: str,
    memory: str,
    stamp: str | None = None,
    *,
    legal_only: bool = False,
    labels: str = "letters",
    think: Any = None,
    memory_k: int = 3,
    memory_visits: bool = False,
) -> str:
    """``<stamp>-<backend>-<mode>-<memory>``, plus ``-legal`` / ``-<labels>`` /
    ``-think-<trigger>-<style>`` when not default."""
    extra = ("-legal" if legal_only else "") + ("" if labels == "letters" else f"-{labels}")
    if memory_k != 3:
        extra += f"-k{memory_k}"
    if memory_visits:
        extra += "-visits"
    if think is not None:
        extra += f"-think-{think.trigger}-{think.style}"
    return f"{stamp or utc_stamp()}-{_slug(backend)}-{mode}-{memory}{extra}"


def prefix_digest(prefix: str) -> str:
    return hashlib.sha256(prefix.encode("utf-8")).hexdigest()


def build_report(meta: RunMeta, episodes: list[EpisodeSummary]) -> RunReport:
    return RunReport(meta=meta, summary=summarize_run(episodes), episodes=episodes)


def _fmt(v: Any, pct: bool = False) -> str:
    if v is None:
        return "-"
    if isinstance(v, dict):
        return ", ".join(f"{k} {n}" for k, n in v.items()) or "-"
    if pct:
        return f"{v:.1%}"
    if isinstance(v, float):
        return f"{v:.2f}"
    return str(v)


HEADLINE = [
    ("episodes", "episodes", False),
    ("ticks", "ticks", False),
    ("completion", "completion", True),
    ("died", "died", True),
    ("timed out", "timed_out", True),
    ("cut short", "cut_short", True),
    ("oracle agreement", "agreement", True),
    ("steps / oracle steps", "steps_over_oracle", False),
    ("distinct cells / steps", "distinct_cell_ratio", False),
    ("reversals / episode", "reversals_per_episode", False),
    ("decisions/s", "decisions_per_s", False),
    ("p50 / p95 total ms", ("p50_total_ms", "p95_total_ms"), False),
    ("p50 / p95 backend ms", ("p50_backend_ms", "p95_backend_ms"), False),
    ("tokens / observation", "tokens_per_observation", False),
    ("mean cached tokens", "mean_cached_tokens", False),
    ("mean top probability", "mean_top_probability", False),
    ("mean options offered", "mean_options_offered", False),
    ("plans (truncated)", ("plans", "plans_truncated"), False),
    ("plan tokens / plan", "plan_tokens_per_plan", False),
    ("planning s / share of time", ("planning_s", "planning_share"), False),
    ("tokens / episode", "tokens_per_episode", False),
    ("plan reasons", "plan_reasons", False),
    ("P(pause) mean / p50 / p90", ("pause_p_mean", "pause_p_p50", "pause_p_p90"), False),
    ("P(plan) mean / p50 / p90", ("plan_p_mean", "plan_p_p50", "plan_p_p90"), False),
]

#: The cross-run table (story 5.4): quality and cost side by side.
COMPARE = [
    ("completion", "completion", True),
    ("died", "died", True),
    ("agreement", "agreement", True),
    ("distinct/steps", "distinct_cell_ratio", False),
    ("decisions/s", "decisions_per_s", False),
    ("options", "mean_options_offered", False),
    ("plans/ep", "plans_per_episode", False),
    ("plan tok/plan", "plan_tokens_per_plan", False),
    ("planning share", "planning_share", True),
    ("tokens/ep", "tokens_per_episode", False),
    ("P(pause) mean", "pause_p_mean", False),
    ("P(plan) mean", "plan_p_mean", False),
]


def run_label(meta: RunMeta) -> str:
    """A short row label: labels, legal-only, memory knobs, think settings."""
    parts = [meta.labels, "legal" if meta.legal_only else "all-actions", meta.memory]
    if meta.memory_k != 3:
        parts.append(f"k={meta.memory_k}")
    if meta.memory_visits:
        parts.append("visits")
    t = meta.think
    if t and t["trigger"] == "rule":
        rules = [f"every {t['replan_every']}"] if t.get("replan_every") else []
        rules += ["damage"] if t.get("replan_on_damage") else []
        if t.get("replan_on_reversals"):
            rules.append(f"reversals {t['replan_on_reversals']}")
        parts.append(f"think rule({', '.join(rules)})/{t['style']}/{t['cost']}")
    else:
        parts.append(f"think {t['trigger']}/{t['style']}/{t['cost']}" if t else "think never")
    if meta.planner_model and meta.planner_model != meta.model:
        parts.append(f"planner {meta.planner_model.split('/')[-1]}")
    return ", ".join(parts)


def comparison_table(reports: list[RunReport]) -> str:
    """One markdown table, a row per run."""
    head = "| run | " + " | ".join(label for label, _, _ in COMPARE) + " |"
    rows = [head, "|" + "---|" * (len(COMPARE) + 1)]
    for r in reports:
        cells = [_fmt(getattr(r.summary, f), pct) for _, f, pct in COMPARE]
        rows.append(f"| {run_label(r.meta)} | " + " | ".join(cells) + " |")
    return "\n".join(rows)


def headline_table(summary: RunSummary) -> str:
    rows = ["| metric | value |", "|---|---|"]
    for label, field, pct in HEADLINE:
        if isinstance(field, tuple):
            value = " / ".join(_fmt(getattr(summary, f)) for f in field)
        else:
            value = _fmt(getattr(summary, field), pct)
        rows.append(f"| {label} | {value} |")
    return "\n".join(rows)


def to_markdown(report: RunReport) -> str:
    m, s = report.meta, report.summary
    power = ", ".join(f"{k} {v}" for k, v in m.power.items())
    lines = [
        f"# Run {m.name}",
        "",
        f"- backend: `{m.backend}`" + (f" (model `{m.model}`)" if m.model else ""),
        f"- planner: `{m.planner}`" + (f" (model `{m.planner_model}`)" if m.planner_model else "")
        if m.planner
        else "- planner: none",
        (
            f"- mode: {m.mode}; memory: {m.memory} (k {m.memory_k}, visits "
            f"{'on' if m.memory_visits else 'off'}); labels: {m.labels}; "
            f"legal-only: {'on' if m.legal_only else 'off'}"
        ),
        f"- git rev: {m.git_rev or '-'}; power: {power}",
        "- think: " + (", ".join(f"{k} {v}" for k, v in m.think.items()) if m.think else "never"),
        (
            f"- map: {m.config.width}x{m.config.height}, {m.config.n_monsters} monsters, "
            f"tick limit {m.config.tick_limit}; "
            f"tick order: {'damage first' if m.config.damage_before_goal else 'goal first'}"
        ),
        f"- prefix: {m.prefix_chars} chars, sha256 {m.prefix_sha256[:12]}"
        + (
            "; versions "
            + ", ".join(f"v{v['version']} {v['sha256'][:12]}" for v in m.prefix_versions)
            if len(m.prefix_versions) > 1
            else ""
        ),
        f"- started {m.started}; finished {m.finished or '-'}"
        + ("; **interrupted**" if m.interrupted else ""),
        "",
        "## Headline",
        "",
        headline_table(s),
        "",
        "## Episodes",
        "",
        (
            "| seed | outcome | steps | oracle steps | agreement | distinct/steps | reversals "
            "| decisions/s | p50 ms | tokens/obs | plans |"
        ),
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for e in report.episodes:
        lines.append(
            f"| {e.seed} | {e.outcome} | {e.steps} | {_fmt(e.oracle_steps)} "
            f"| {_fmt(e.agreement, True)} | {_fmt(e.distinct_cell_ratio)} | {e.reversals} "
            f"| {_fmt(e.decisions_per_s)} | {_fmt(e.p50_total_ms)} "
            f"| {_fmt(e.tokens_per_observation)} | {e.plan_count} |"
        )
    return "\n".join(lines) + "\n"


def write_report(report: RunReport, out_dir: str | Path = "runs") -> tuple[Path, Path]:
    """Write ``<out_dir>/<name>.md`` and ``.json``; return both paths."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    md, js = out / f"{report.meta.name}.md", out / f"{report.meta.name}.json"
    md.write_text(to_markdown(report), encoding="utf-8")
    js.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return md, js
