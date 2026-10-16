"""Live view (story 2.4): watch an episode, live or from a replay file.

The window is a thin pygame shell. Every pixel comes from :func:`render_frame`,
a pure Pillow function: on the left the map exactly as
:func:`~gridworld.render.image.to_image` draws it (the PNG a vision backend
sees, scaled up with nearest-neighbour), on the right a panel with hp and tick,
decisions/s, and six probability bars in wire order (north, south, east, west,
attack, wait), plus a seventh ``plan`` bar when the probabilities carry
P(plan) (story 5.7's ``--think action``). The taken action's bar is drawn in its action colour (the
others grey); the oracle's action is outlined in white. Because the frame is a
PIL image, all of it is testable headless and the window cannot drift from
the renderer (ADR-0001).

``decisions/s`` is computed from recorded ``timing`` (milliseconds per phase;
``total_ms`` or ``total`` if present, else the sum of phases) over every tick seen so far, so
a replay shows the speed of the original run, not of the playback. It reads
``-`` until a tick with timing arrives.

Story 4.8: when a session hands the view its
:class:`~gridworld.harness.prompts.PrefixSource` (``prefix``), the tallies end
with ``prefix v<N> (file|default)`` and, for :data:`RELOAD_NOTE_S` seconds after
a hot reload, ``prefix reloaded at tick T``. P calls ``on_prefix_key`` (the
session's :func:`~gridworld.harness.prompts.edit_prefix`).

pygame (the ``view`` extra) is imported only when a window opens;
:class:`ViewUnavailable` names the extra to install.
"""

from __future__ import annotations

import os
import time
from collections import deque
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from types import TracebackType
from typing import Any, Self

from PIL import Image, ImageDraw, ImageFont

from .harness.route import plan_for_tail, strip_action_line
from .record import read_episode, replay
from .render.image import to_image
from .render.tiles import ACTION_COLOURS
from .sim import Action, Observation

__all__ = ["DecisionRate", "LiveView", "ViewUnavailable", "play_file", "render_frame"]

PANEL_WIDTH = 260
PANEL_BG = (24, 24, 28)
BAR_BG = (52, 52, 60)
BAR_OTHER = (120, 120, 132)
TEXT = (230, 230, 230)
ORACLE_OUTLINE = (255, 255, 255)
BANNER_BG = (16, 16, 20)
INFO_Y = 60 + 6 * 28 + 16
END_FLASH = {"goal": "WON", "dead": "DIED", "timeout": "TIMED OUT"}  # by EpisodeEnd.reason
RECENT_TICKS = 10  # the rolling "now X/s" window (story 1.5)
PLAN_BAR = (90, 160, 240)  # the plan option's bar (story 5.7)
DROPPED = (200, 160, 90)  # "plan dropped (...)" in the plan panel (story 5.8)
PLAN_HEAD = (150, 200, 255)
TRUNCATED = (214, 40, 96)  # distinct from the hp pips
THINKING = (250, 200, 40)
STRIP_TICK = (70, 70, 80)
STRIP_PLAN = (150, 200, 255)
STRIP_NOW = (255, 255, 255)
STRIP_CELL = 4
STRIP_LEN = (PANEL_WIDTH - 24) // STRIP_CELL
PLAN_WRAP = 38
PLAN_LINES = 9
RELOAD_NOTE_S = 4.0  # how long "prefix reloaded at tick T" stays up (story 4.8)


class ViewUnavailable(ImportError):
    """pygame is not installed."""


def _pygame():
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    try:
        import pygame
    except ImportError as exc:
        raise ViewUnavailable(
            "the live view needs pygame: pip install 'systemone-gridworld[view]'"
        ) from exc
    return pygame


class DecisionRate:
    """Decisions per second from per-tick ``timing`` dicts (milliseconds).

    :attr:`per_second` is the session figure: every tick's whole time,
    planning and each map's first full prefill included. :attr:`recent_per_second`
    (story 1.5, shown as ``now X/s``) is a rolling rate over the last
    :data:`RECENT_TICKS` ticks with planning time (``think_ms``) taken out.
    """

    def __init__(self) -> None:
        self.decisions = 0
        self.total_ms = 0.0
        self.recent: deque[float] = deque(maxlen=RECENT_TICKS)

    def add(self, timing: Mapping[str, float] | None) -> None:
        if not timing:
            return
        self.decisions += 1
        total = next((timing[k] for k in ("total_ms", "total") if k in timing), None)
        if total is None:
            total = sum(timing.values())
        self.total_ms += total
        self.recent.append(max(0.0, total - timing.get("think_ms", 0.0)))

    @property
    def recent_per_second(self) -> float | None:
        spent = sum(self.recent)
        return len(self.recent) / (spent / 1000) if self.recent and spent > 0 else None

    @property
    def recent_tick_s(self) -> float | None:
        """Mean seconds per recent decision tick (the live frame interval)."""
        return sum(self.recent) / len(self.recent) / 1000 if self.recent else None

    @property
    def per_second(self) -> float | None:
        if not self.decisions or self.total_ms <= 0:
            return None
        return self.decisions / (self.total_ms / 1000)


def render_frame(
    obs: Observation,
    *,
    probabilities: Mapping[Action | str, float] | None = None,
    action: Action | None = None,
    oracle_action: Action | None = None,
    decisions_per_s: float | None = None,
    info_lines: Sequence[str] = (),
    banner: str | None = None,
    recent_per_s: float | None = None,
    plan_text: str | None = None,
    plan_truncated: bool = False,
    thinking: bool = False,
    plan_ticks: Sequence[int] | None = None,
    plan_dropped: str | None = None,
    tile: int = 16,
    scale: int = 3,
) -> Image.Image:
    """The full window contents as an RGB image (pure; no pygame).

    ``info_lines`` are drawn under the bars (session tallies in continuous
    play); ``banner`` is a centred box over the map (the end-of-episode flash).

    System Two (story 5.3), drawn when ``plan_ticks`` is not ``None``: a plan
    panel under the tallies with the current plan wrapped, a red
    ``[truncated]`` badge when the last plan hit its cap, a yellow
    ``thinking...`` state (also as a banner over the map) while a plan call
    runs, and a tick strip of the last ticks with planning ticks marked.
    Story 5.8: the plan text carries the remaining route as the decider saw it;
    ``plan_dropped`` (``exhausted`` / ``deviated``) replaces it with a
    ``plan dropped (<why>)`` state until the next plan.
    """
    plan_p = (probabilities or {}).get("plan")
    rows: list[Action | str] = [*Action, *(["plan"] if plan_p is not None else [])]
    info_y = INFO_Y + 28 * (len(rows) - len(Action))
    board = to_image(obs, tile)
    board = board.resize((board.width * scale, board.height * scale), Image.Resampling.NEAREST)
    plan_y = info_y + 18 * len(info_lines) + 12
    system_two = plan_ticks is not None
    plan_h = 16 + 16 * PLAN_LINES + 24 if system_two else 0
    height = max(board.height, (len(rows) + 2) * 28 + 24, plan_y + plan_h)
    frame = Image.new("RGB", (board.width + PANEL_WIDTH, height), PANEL_BG)
    frame.paste(board, (0, 0))
    draw = ImageDraw.Draw(frame)
    font = ImageFont.load_default()
    x0 = board.width + 12
    rate = "-" if decisions_per_s is None else f"{decisions_per_s:.1f}"
    draw.text((x0, 10), f"tick {obs.tick}   hp {obs.player_hp}", fill=TEXT, font=font)
    now = "" if recent_per_s is None else f"   now {recent_per_s:.1f}/s"
    draw.text((x0, 30), f"decisions/s {rate}{now}", fill=TEXT, font=font)
    probs = {(k if k == "plan" else Action(k)): v for k, v in (probabilities or {}).items()}
    bar_x, bar_w, bar_h = x0 + 56, PANEL_WIDTH - 56 - 24, 16
    for i, a in enumerate(rows):
        y = 60 + i * 28
        draw.text((x0, y + 2), getattr(a, "value", a), fill=TEXT, font=font)
        draw.rectangle((bar_x, y, bar_x + bar_w - 1, y + bar_h - 1), fill=BAR_BG)
        p = probs.get(a)
        if p is not None:
            fill = PLAN_BAR if a == "plan" else ACTION_COLOURS[a] if a == action else BAR_OTHER
            w = round(max(0.0, min(1.0, p)) * bar_w)
            if w:
                draw.rectangle((bar_x, y, bar_x + w - 1, y + bar_h - 1), fill=fill)
        elif a == action:
            draw.rectangle((bar_x, y, bar_x + 5, y + bar_h - 1), fill=ACTION_COLOURS[a])
        if a == oracle_action:
            draw.rectangle(
                (bar_x - 3, y - 3, bar_x + bar_w + 2, y + bar_h + 2),
                outline=ORACLE_OUTLINE,
                width=2,
            )
    for i, line in enumerate(info_lines):
        draw.text((x0, info_y + i * 18), line, fill=TEXT, font=font)
    if system_two:
        _plan_panel(
            draw,
            font,
            x0,
            plan_y,
            obs.tick,
            plan_text,
            plan_truncated,
            thinking,
            plan_ticks,
            plan_dropped,
        )
        if thinking and not banner:
            banner = "thinking..."
    if banner:
        left, top, right, bottom = draw.textbbox((0, 0), banner, font=font)
        w, h = right - left + 40, bottom - top + 24
        bx, by = (board.width - w) // 2, (board.height - h) // 2
        draw.rectangle((bx, by, bx + w, by + h), fill=BANNER_BG, outline=ORACLE_OUTLINE, width=2)
        draw.text((bx + 20 - left, by + 12 - top), banner, fill=TEXT, font=font)
    return frame


def _plan_panel(
    draw, font, x0, y0, tick, text, truncated, thinking, plan_ticks, dropped=None
) -> None:
    import textwrap

    draw.text((x0, y0), "plan", fill=PLAN_HEAD, font=font)
    if truncated:
        draw.rectangle((x0 + 40, y0 - 1, x0 + 118, y0 + 13), fill=TRUNCATED)
        draw.text((x0 + 44, y0), "[truncated]", fill=TEXT, font=font)
    if thinking:
        draw.rectangle((x0 + 128, y0 + 1, x0 + 138, y0 + 11), fill=THINKING)
        draw.text((x0 + 144, y0), "thinking...", fill=THINKING, font=font)
    if dropped:
        draw.rectangle((x0, y0 + 17, x0 + 10, y0 + 27), fill=DROPPED)
        draw.text((x0 + 16, y0 + 16), f"plan dropped ({dropped})", fill=DROPPED, font=font)
    else:
        lines = textwrap.wrap(text or "(none yet)", PLAN_WRAP)[:PLAN_LINES]
        for i, line in enumerate(lines):
            draw.text((x0, y0 + 16 + 16 * i), line, fill=TEXT, font=font)
    sy = y0 + 16 + 16 * PLAN_LINES + 6
    start = max(0, tick - STRIP_LEN + 1)
    marked = set(plan_ticks or ())
    for i, t in enumerate(range(start, tick + 1)):
        colour = STRIP_NOW if t == tick else STRIP_PLAN if t in marked else STRIP_TICK
        x = x0 + i * STRIP_CELL
        h = 12 if t in marked else 6
        draw.rectangle((x, sy + 12 - h, x + STRIP_CELL - 2, sy + 11), fill=colour)


class LiveView:
    """A pygame window fed one observation at a time (a live loop or :func:`play_file`).

    :meth:`update` returns ``False`` once the user closes the window or presses
    Esc/q, so a driving loop can stop. ``fps`` > 0 caps the update rate.
    """

    def __init__(
        self, *, tile: int = 16, scale: int = 3, fps: float = 0.0, caption: str = "gridworld"
    ):
        self._pg = _pygame()
        self._pg.display.init()
        self._pg.display.set_caption(caption)
        self._clock = self._pg.time.Clock()
        self._screen = None
        self.tile, self.scale, self.fps = tile, scale, fps
        self.rate = DecisionRate()
        self.last_frame: Image.Image | None = None
        self.last_obs: Observation | None = None
        #: Lines drawn under the bars on every frame (session tallies).
        self.info_lines: list[str] = []
        #: System Two state (story 5.3); ``plan_ticks`` is None until a planner is in play.
        self.plan_text: str | None = None
        self.plan_truncated = False
        self.plan_ticks: list[int] | None = None
        self.plan_dropped: str | None = None
        #: Story 4.8: the session's PrefixSource, the P-key action, the last reload.
        self.prefix: Any = None
        self.on_prefix_key: Callable[[], Any] | None = None
        self.reload_note: tuple[int, float] | None = None
        self.open = True

    def _pump(self) -> bool:
        pg = self._pg
        for event in pg.event.get():
            if event.type == pg.QUIT or (
                event.type == pg.KEYDOWN and event.key in (pg.K_ESCAPE, pg.K_q)
            ):
                self.open = False
            elif event.type == pg.KEYDOWN and event.key == pg.K_p and self.on_prefix_key:
                self.on_prefix_key()
        return self.open

    def prefix_reloaded(self, tick: int, version: int) -> None:
        """The loop's notice that prefix ``version`` took effect on ``tick``."""
        self.reload_note = (tick, time.monotonic())

    def prefix_lines(self) -> list[str]:
        """``prefix v<N> (file|default)``, plus the reload note while it is fresh."""
        if self.prefix is None:
            return []
        lines = [f"prefix v{self.prefix.version} ({self.prefix.kind})"]
        if self.reload_note and time.monotonic() - self.reload_note[1] < RELOAD_NOTE_S:
            lines.append(f"prefix reloaded at tick {self.reload_note[0]}")
        return lines

    def _info(self) -> list[str]:
        return [*self.info_lines, *self.prefix_lines()]

    def update(
        self,
        obs: Observation,
        probabilities: Mapping[Action | str, float] | None = None,
        action: Action | None = None,
        oracle_action: Action | None = None,
        timing: Mapping[str, float] | None = None,
    ) -> bool:
        """Draw one tick; returns whether the window is still open."""
        if not self._pump():
            return False
        self.rate.add(timing)
        self.last_obs = obs
        self._show(
            render_frame(
                obs,
                probabilities=probabilities,
                action=action,
                oracle_action=oracle_action,
                decisions_per_s=self.rate.per_second,
                recent_per_s=self.rate.recent_per_second,
                info_lines=self._info(),
                **self._plan_kwargs(),
                tile=self.tile,
                scale=self.scale,
            )
        )
        if self.fps > 0:
            self._clock.tick(self.fps)
        return True

    def flash(self, text: str, seconds: float = 1.0, obs: Observation | None = None) -> bool:
        """Show ``text`` over the map for ``seconds`` (pumping events); returns ``open``."""
        obs = obs or self.last_obs
        if obs is None or not self._pump():
            return self.open
        self._show(
            render_frame(
                obs,
                decisions_per_s=self.rate.per_second,
                recent_per_s=self.rate.recent_per_second,
                info_lines=self._info(),
                banner=text,
                **self._plan_kwargs(),
                tile=self.tile,
                scale=self.scale,
            )
        )
        end = time.monotonic() + seconds
        while time.monotonic() < end and self._pump():
            self._clock.tick(30)
        return self.open

    def _plan_kwargs(self, thinking: bool = False) -> dict:
        return {
            "plan_text": self.plan_text,
            "plan_truncated": self.plan_truncated,
            "thinking": thinking,
            "plan_ticks": self.plan_ticks,
            "plan_dropped": self.plan_dropped,
        }

    def set_plan(
        self, tick: int | None, text: str | None, truncated: bool, *, reset: bool = False
    ) -> None:
        """Record a plan made on ``tick`` (``reset`` starts a new episode's plan state)."""
        if reset or self.plan_ticks is None:
            self.plan_ticks, self.plan_text, self.plan_truncated = [], None, False
            self.plan_dropped = None
        if tick is not None:
            self.plan_ticks.append(tick)
            self.plan_truncated = truncated
            if text:
                self.plan_text, self.plan_dropped = text, None

    def show_plan(self, text: str | None, dropped: str | None = None) -> None:
        """Story 5.8: the plan as the decider sees it this tick (remaining route), or
        the ``plan dropped (<why>)`` state when ``dropped`` is set."""
        if self.plan_ticks is None:
            self.plan_ticks = []
        self.plan_text, self.plan_dropped = text, dropped

    def thinking(self, obs: Observation) -> bool:
        """Show the thinking state before a (blocking) plan call; returns ``open``."""
        if not self._pump():
            return False
        if self.plan_ticks is None:
            self.plan_ticks = []
        self._show(
            render_frame(
                obs,
                decisions_per_s=self.rate.per_second,
                recent_per_s=self.rate.recent_per_second,
                info_lines=self._info(),
                **self._plan_kwargs(thinking=True),
                tile=self.tile,
                scale=self.scale,
            )
        )
        return True

    def _show(self, frame: Image.Image) -> None:
        pg = self._pg
        if self._screen is None or self._screen.get_size() != frame.size:
            self._screen = pg.display.set_mode(frame.size)
        self._screen.blit(pg.image.frombytes(frame.tobytes(), frame.size, "RGB"), (0, 0))
        pg.display.flip()
        self.last_frame = frame

    def hold_frame(self) -> bool:
        """Keep the current frame up for one normal frame interval (story 1.5: the
        final frame before the result flash). With ``fps`` the last :meth:`update`
        already waited; otherwise wait one recent decision tick (0.1 to 1 s)."""
        if self.fps > 0:
            return self.open
        seconds = min(1.0, max(0.1, self.rate.recent_tick_s or 0.25))
        end = time.monotonic() + seconds
        while time.monotonic() < end and self._pump():
            self._clock.tick(60)
        return self.open

    def hold(self) -> None:
        """Keep the last frame up until the window is closed."""
        while self._pump():
            self._clock.tick(30)

    def close(self) -> None:
        self._pg.display.quit()
        self.open = False

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()


def play_file(
    path: str | Path,
    *,
    fps: float = 4.0,
    tile: int = 16,
    scale: int = 3,
    verify: bool = True,
    hold: bool = False,
    flash_s: float = 1.0,
) -> int:
    """Play an episode file in a window, no backend needed; returns the frames shown.

    With ``verify`` the file is first re-stepped through the simulator
    (:func:`~gridworld.record.replay`), so what you watch is proven reproducible.
    Recorded plans drive the plan panel: the text changes on the ticks where a
    plan was made, and those ticks are marked on the strip.
    """
    if verify:
        for _ in replay(path):
            pass
    episode = read_episode(path)
    shown = 0
    with LiveView(
        tile=tile, scale=scale, fps=fps, caption=f"gridworld — {Path(path).name}"
    ) as view:
        if any(t.plan or t.pause_p is not None or t.plan_p is not None for t in episode.ticks):
            view.set_plan(None, None, False, reset=True)
        raw: str | None = None
        for t in episode.ticks:
            if t.plan_dropped:
                raw = None
                view.show_plan(None, t.plan_dropped)
            if t.plan:
                text = strip_action_line(t.plan.get("plan", ""))
                truncated = bool(t.plan.get("truncated"))
                if text and not truncated:
                    raw = text
                view.set_plan(
                    t.observation.tick, None if truncated else " ".join(text.split()), truncated
                )
            if raw is not None and t.route_remaining is not None:
                remaining = [Action(a) for a in t.route_remaining]
                view.show_plan(" ".join(plan_for_tail(raw, remaining).split()))
            probs = t.probabilities
            if t.plan_p is not None:
                probs = {**(probs or {}), "plan": t.plan_p}
            if not view.update(t.observation, probs, t.action, t.oracle_action, t.timing):
                return shown
            shown += 1
        if episode.end is not None:
            last = episode.ticks[-1] if episode.ticks else None
            probs = last.probabilities if last else None
            if last is not None and last.plan_p is not None:
                probs = {**(probs or {}), "plan": last.plan_p}
            args = (probs, last.action, last.oracle_action) if last else ()
            # Story 1.5: the final frame with the last tick's bars, then the result
            if not view.update(episode.end.observation, *args):
                return shown
            shown += 1
            view.hold_frame()
            text = END_FLASH.get(episode.end.reason, episode.end.reason.upper())
            view.flash(f"seed {episode.header.seed}: {text}", flash_s)
        if hold:
            view.hold()
    return shown
