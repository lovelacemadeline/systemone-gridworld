"""Sessions (story 4.3): N episodes, or forever, with one report.

:func:`run_session` plays seeds ``seed, seed + 1, ...``; ``episodes=0`` means
until stopped. Each episode is recorded to ``<out_dir>/<name>/seed-NNNN.jsonl``
as it runs, and the report (``<out_dir>/<name>.md`` / ``.json``) is rewritten
after every episode and once more on exit, so stopping early loses nothing.

Stopping: the view closing (Esc, q, window close), ``on_episode`` returning
``False``, or a KeyboardInterrupt (the report is then marked interrupted and
the interrupt is not re-raised). With a view, each episode ends with a short
result flash (won / died / timed out), and the side panel carries session
tallies: episodes, win rate, steps over oracle steps, oscillation and
decisions/s over the session.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..backends.base import Backend
from ..backends.request import Mode
from ..record import git_rev
from ..sim import GridWorld, WorldConfig
from .loop import Hooks, run_episode
from .memory import make_memory
from .plan import Planner
from .prompts import DEFAULT_PREFIX
from .provenance import power_state
from .report import RunMeta, RunReport, build_report, prefix_digest, run_name, write_report
from .score import EpisodeSummary, summarize_run
from .think import SystemTwo, ThinkConfig

__all__ = ["FLASH", "SessionResult", "run_session", "session_lines"]

FLASH = {
    "won": "WON",
    "died": "DIED",
    "timeout": "TIMED OUT",
    "max_ticks": "TICK CAP",
    "stopped": "STOPPED",
}


class SessionResult:
    def __init__(self, report: RunReport, md: Path, json: Path, episode_dir: Path) -> None:
        self.report, self.md, self.json, self.episode_dir = report, md, json, episode_dir


def _f(v: float | None, spec: str) -> str:
    return "-" if v is None else format(v, spec)


def session_lines(eps: list[EpisodeSummary]) -> list[str]:
    """The panel's session tallies."""
    s = summarize_run(eps)
    return [
        "session",
        f"episodes {s.episodes}   win {_f(s.completion, '.0%') if eps else '-'}",
        f"steps/oracle {_f(s.steps_over_oracle, '.2f')}",
        f"distinct/steps {_f(s.distinct_cell_ratio, '.2f')}",
        f"reversals/ep {_f(s.reversals_per_episode, '.1f')}",
        f"decisions/s {_f(s.decisions_per_s, '.1f')}",
    ]


def run_session(
    backend: Backend,
    *,
    mode: Mode = "text",
    memory: str = "none",
    prefix: str = DEFAULT_PREFIX,
    episodes: int = 5,
    seed: int = 0,
    out_dir: str | Path = "runs",
    config: WorldConfig | None = None,
    view: Any = None,
    hooks: Hooks | None = None,
    max_ticks: int | None = None,
    on_episode: Callable[[EpisodeSummary], bool] | None = None,
    flash_s: float = 1.0,
    legal_only: bool = False,
    labels: str = "letters",
    think: ThinkConfig | None = None,
    planner: Planner | None = None,
) -> SessionResult:
    """Play a session and write its report (see the module docstring)."""
    world = GridWorld(config)
    rev = git_rev()
    thinking = think is not None and think.trigger != "never"
    if thinking and planner is None:
        raise ValueError("a think trigger needs a planner")
    name = run_name(
        backend.id,
        mode,
        memory,
        legal_only=legal_only,
        labels=labels,
        think=think if thinking else None,
    )
    label_style = {"letters": None, "words": "option-text"}[labels]
    out = Path(out_dir)
    episode_dir = out / name
    started = datetime.now(UTC).isoformat(timespec="seconds")
    eps: list[EpisodeSummary] = []
    interrupted = False

    def meta(finished: bool) -> RunMeta:
        return RunMeta(
            name=name,
            backend=backend.id,
            model=getattr(backend, "model_id", None),
            mode=mode,
            memory=memory,
            legal_only=legal_only,
            labels=labels,
            think=asdict(think) if thinking else None,
            git_rev=rev,
            power=power_state(),
            config=world.config,
            prefix_chars=len(prefix),
            prefix_sha256=prefix_digest(prefix),
            started=started,
            finished=datetime.now(UTC).isoformat(timespec="seconds") if finished else None,
            interrupted=interrupted,
        )

    i = 0
    try:
        while episodes == 0 or i < episodes:
            if view is not None:
                view.info_lines = session_lines(eps)
            episode_hooks = hooks
            if thinking:
                two = SystemTwo(planner, think, prefix, view=view)
                episode_hooks = two.hooks(after_tick=hooks.after_tick if hooks else None)
                if view is not None and hasattr(view, "set_plan"):
                    view.set_plan(None, None, False, reset=True)
            s = run_episode(
                world,
                backend,
                seed=seed + i,
                mode=mode,
                prefix=prefix,
                memory=make_memory(memory),
                record_path=episode_dir / f"seed-{seed + i:04d}.jsonl",
                view=view,
                hooks=episode_hooks,
                max_ticks=max_ticks,
                rev=rev,
                legal_only=legal_only,
                label_style=label_style,
            )
            eps.append(s)
            i += 1
            write_report(build_report(meta(False), eps), out)
            if s.outcome == "stopped":
                break
            if view is not None:
                view.info_lines = session_lines(eps)
                if not view.flash(f"seed {s.seed}: {FLASH.get(s.outcome, s.outcome)}", flash_s):
                    break
            if on_episode is not None and on_episode(s) is False:
                break
    except KeyboardInterrupt:
        interrupted = True
    report = build_report(meta(True), eps)
    md, js = write_report(report, out)
    return SessionResult(report, md, js, episode_dir)
