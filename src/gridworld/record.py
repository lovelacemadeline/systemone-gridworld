"""Episode recording and replay (story 1.4): JSONL files a viewer can play back.

One JSON object per line, discriminated by ``kind``::

    {"kind": "header", "v": 1, "seed": 7, "config": {...WorldConfig...},
     "backend": "fake", "mode": "text", "git_rev": "d130342"}
    {"kind": "tick", "observation": {...}, "action": "east",
     "probabilities": {"north": 0.1, ...} | null, "oracle_action": "east",
     "timing": {"render": 0.2, "backend": 31.0, "step": 0.1} | null}
    ...
    {"kind": "end", "observation": {...}, "reward": 1, "reason": "goal"}

``usage`` on a tick line (the backend's token counts) and ``offered`` (the
actions the request offered, story 4.5) are optional, as is the
header's ``memory`` mode (default ``none``); both are additive within v1.
An ``end`` reason other than goal/dead/timeout (``stopped``, ``max_ticks``)
marks an episode the harness cut short.

A ``tick`` line holds the observation the decision was made on and the action
taken from it; the first one is ``GridWorld.reset(seed)``. The ``end`` line
holds the terminal observation (written by :meth:`EpisodeRecorder.end`; absent
if the run was cut short). ``timing`` values are milliseconds.

:func:`replay` re-steps a fresh :class:`~gridworld.sim.GridWorld` with the
recorded actions and raises :class:`ReplayMismatch` at the first observation
that differs, so a file is proof of its own reproducibility.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path
from types import TracebackType
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, TypeAdapter

from .sim import Action, GridWorld, Observation, StepResult, WorldConfig

__all__ = [
    "Episode",
    "EpisodeEnd",
    "EpisodeHeader",
    "EpisodeRecorder",
    "ReplayMismatch",
    "TickRecord",
    "git_rev",
    "read_episode",
    "record_episode",
    "replay",
]

VERSION = 1

#: End reasons the simulator itself produces; anything else is a harness cut-off.
SIM_REASONS = ("goal", "dead", "timeout")


class EpisodeHeader(BaseModel):
    """First line: everything needed to rebuild the starting state, plus provenance."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["header"] = "header"
    v: int = VERSION
    seed: int
    config: WorldConfig
    backend: str
    mode: str
    memory: str = "none"
    #: System Two's planner id when it differs from the backend (story 5.5), else None.
    planner: str | None = None
    git_rev: str | None = None


class TickRecord(BaseModel):
    """One decision: the observation it saw, the action taken, and how it was reached."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["tick"] = "tick"
    observation: Observation
    action: Action
    probabilities: dict[Action, float] | None = None
    oracle_action: Action
    timing: dict[str, float] | None = None
    usage: dict[str, int] | None = None
    offered: tuple[Action, ...] | None = None
    #: System Two (Epic 5): P(yes) of the pause_to_plan question, and the plan made here.
    pause_p: float | None = None
    plan: dict[str, Any] | None = None


class EpisodeEnd(BaseModel):
    """Last line: the terminal observation and how the episode ended."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["end"] = "end"
    observation: Observation
    reward: int
    reason: str


class Episode(BaseModel):
    """A parsed episode file."""

    model_config = ConfigDict(frozen=True)

    header: EpisodeHeader
    ticks: tuple[TickRecord, ...]
    end: EpisodeEnd | None = None


_Line = TypeAdapter(EpisodeHeader | TickRecord | EpisodeEnd)


class ReplayMismatch(AssertionError):
    """A replayed observation differs from the recorded one."""


def git_rev(cwd: str | Path | None = None) -> str | None:
    """Short HEAD commit of the checkout at ``cwd`` (or the process cwd), else ``None``."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.stdout.strip() or None


class EpisodeRecorder:
    """Writes one episode file; use as a context manager. Lines are flushed as written."""

    def __init__(self, path: str | Path, header: EpisodeHeader) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.path.open("w", encoding="utf-8")
        self._write(header)

    def _write(self, record: BaseModel) -> None:
        self._fh.write(record.model_dump_json() + "\n")
        self._fh.flush()

    def tick(
        self,
        observation: Observation,
        action: Action,
        oracle_action: Action,
        probabilities: dict[Action, float] | None = None,
        timing: dict[str, float] | None = None,
        usage: dict[str, int] | None = None,
        offered: tuple[Action, ...] | None = None,
        *,
        pause_p: float | None = None,
        plan: dict[str, Any] | None = None,
    ) -> None:
        """Record the decision taken from ``observation``."""
        self._write(
            TickRecord(
                observation=observation,
                action=action,
                probabilities=probabilities,
                oracle_action=oracle_action,
                timing=timing,
                usage=usage,
                offered=offered,
                pause_p=pause_p,
                plan=plan,
            )
        )

    def end(self, observation: Observation, reward: int, reason: str) -> None:
        """Record the terminal observation."""
        self._write(EpisodeEnd(observation=observation, reward=reward, reason=reason))

    def close(self) -> None:
        self._fh.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()


def record_episode(
    path: str | Path,
    seed: int,
    config: WorldConfig | None = None,
    policy: Callable[[Observation], Action] | None = None,
    *,
    backend: str = "oracle",
    mode: str = "observation",
) -> StepResult:
    """Play ``policy`` (default: the oracle) from ``seed`` and record it to ``path``.

    No probabilities or timing are recorded (a bare policy has neither); the
    harness (Epic 4) records backend episodes with both.
    """
    from .oracle import oracle

    policy = policy or oracle
    world = GridWorld(config)
    obs = world.reset(seed)
    header = EpisodeHeader(
        seed=seed, config=world.config, backend=backend, mode=mode, git_rev=git_rev()
    )
    with EpisodeRecorder(path, header) as rec:
        while True:
            action = policy(obs)
            rec.tick(obs, action, oracle_action=oracle(obs))
            result = world.step(action)
            obs = result.observation
            if result.done:
                rec.end(obs, result.reward, result.info["reason"])
                return result


def read_episode(path: str | Path) -> Episode:
    """Parse an episode file without touching the simulator (what a viewer needs)."""
    lines = [
        _Line.validate_json(raw)
        for raw in Path(path).read_text(encoding="utf-8").splitlines()
        if raw.strip()
    ]
    if not lines or not isinstance(lines[0], EpisodeHeader):
        raise ValueError(f"{path}: first line is not an episode header")
    ticks = tuple(r for r in lines[1:] if isinstance(r, TickRecord))
    ends = [r for r in lines[1:] if isinstance(r, EpisodeEnd)]
    if len(ticks) + len(ends) != len(lines) - 1 or len(ends) > 1:
        raise ValueError(f"{path}: expected header, ticks, then at most one end line")
    if ends and lines[-1] is not ends[0]:
        raise ValueError(f"{path}: end line is not last")
    return Episode(header=lines[0], ticks=ticks, end=ends[0] if ends else None)


def replay(path: str | Path) -> Iterator[Observation]:
    """Re-step the sim with the recorded actions, yielding each verified observation.

    Yields the reset observation, then the observation after each recorded
    action (so the last one is the terminal state when the file has an end
    line). Raises :class:`ReplayMismatch` naming the tick of the first
    disagreement, including a mismatched reward or end reason.
    """
    episode = read_episode(path)
    world = GridWorld(episode.header.config)
    current = world.reset(episode.header.seed)
    recorded = [t.observation for t in episode.ticks]
    if episode.end is not None:
        recorded.append(episode.end.observation)
    result = None
    for i, expected in enumerate(recorded):
        if current != expected:
            raise ReplayMismatch(f"{path}: observation at tick {expected.tick} differs on replay")
        yield current
        if i < len(episode.ticks):
            result = world.step(episode.ticks[i].action)
            current = result.observation
    end = episode.end
    if end is not None and result is not None:
        sim_reason = result.info["reason"]
        # A harness may cut an episode short ("stopped", "max_ticks"): then the sim has
        # not ended it, and the recorded reason must not claim a sim ending.
        if sim_reason is None:
            if end.reason in SIM_REASONS:
                raise ReplayMismatch(f"{path}: end claims {end.reason!r}; the sim had not ended")
        elif (result.reward, sim_reason) != (end.reward, end.reason):
            raise ReplayMismatch(f"{path}: end differs on replay")
