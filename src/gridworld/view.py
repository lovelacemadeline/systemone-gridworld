"""Live view (story 2.4): watch an episode, live or from a replay file.

The window is a thin pygame shell. Every pixel comes from :func:`render_frame`,
a pure Pillow function: on the left the map exactly as
:func:`~gridworld.render.image.to_image` draws it (the PNG a vision backend
sees, scaled up with nearest-neighbour), on the right a panel with hp and tick,
decisions/s, and six probability bars in wire order (north, south, east, west,
attack, wait). The taken action's bar is drawn in its action colour (the
others grey); the oracle's action is outlined in white. Because the frame is a
PIL image, all of it is testable headless and the window cannot drift from
the renderer (ADR-0001).

``decisions/s`` is computed from recorded ``timing`` (milliseconds per phase;
``total_ms`` or ``total`` if present, else the sum of phases) over every tick seen so far, so
a replay shows the speed of the original run, not of the playback. It reads
``-`` until a tick with timing arrives.

pygame (the ``view`` extra) is imported only when a window opens;
:class:`ViewUnavailable` names the extra to install.
"""

from __future__ import annotations

import os
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import TracebackType
from typing import Self

from PIL import Image, ImageDraw, ImageFont

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
    """Running decisions per second from per-tick ``timing`` dicts (milliseconds)."""

    def __init__(self) -> None:
        self.decisions = 0
        self.total_ms = 0.0

    def add(self, timing: Mapping[str, float] | None) -> None:
        if not timing:
            return
        self.decisions += 1
        for key in ("total_ms", "total"):
            if key in timing:
                self.total_ms += timing[key]
                return
        self.total_ms += sum(timing.values())

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
    tile: int = 16,
    scale: int = 3,
) -> Image.Image:
    """The full window contents as an RGB image (pure; no pygame).

    ``info_lines`` are drawn under the bars (session tallies in continuous
    play); ``banner`` is a centred box over the map (the end-of-episode flash).
    """
    board = to_image(obs, tile)
    board = board.resize((board.width * scale, board.height * scale), Image.Resampling.NEAREST)
    height = max(board.height, 8 * 28 + 24, INFO_Y + 18 * len(info_lines) + 12)
    frame = Image.new("RGB", (board.width + PANEL_WIDTH, height), PANEL_BG)
    frame.paste(board, (0, 0))
    draw = ImageDraw.Draw(frame)
    font = ImageFont.load_default()
    x0 = board.width + 12
    rate = "-" if decisions_per_s is None else f"{decisions_per_s:.1f}"
    draw.text((x0, 10), f"tick {obs.tick}   hp {obs.player_hp}", fill=TEXT, font=font)
    draw.text((x0, 30), f"decisions/s {rate}", fill=TEXT, font=font)
    probs = {Action(k): v for k, v in (probabilities or {}).items()}
    bar_x, bar_w, bar_h = x0 + 56, PANEL_WIDTH - 56 - 24, 16
    for i, a in enumerate(Action):
        y = 60 + i * 28
        draw.text((x0, y + 2), a.value, fill=TEXT, font=font)
        draw.rectangle((bar_x, y, bar_x + bar_w - 1, y + bar_h - 1), fill=BAR_BG)
        p = probs.get(a)
        if p is not None:
            fill = ACTION_COLOURS[a] if a == action else BAR_OTHER
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
        draw.text((x0, INFO_Y + i * 18), line, fill=TEXT, font=font)
    if banner:
        left, top, right, bottom = draw.textbbox((0, 0), banner, font=font)
        w, h = right - left + 40, bottom - top + 24
        bx, by = (board.width - w) // 2, (board.height - h) // 2
        draw.rectangle((bx, by, bx + w, by + h), fill=BANNER_BG, outline=ORACLE_OUTLINE, width=2)
        draw.text((bx + 20 - left, by + 12 - top), banner, fill=TEXT, font=font)
    return frame


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
        self.open = True

    def _pump(self) -> bool:
        pg = self._pg
        for event in pg.event.get():
            if event.type == pg.QUIT or (
                event.type == pg.KEYDOWN and event.key in (pg.K_ESCAPE, pg.K_q)
            ):
                self.open = False
        return self.open

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
                info_lines=self.info_lines,
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
                info_lines=self.info_lines,
                banner=text,
                tile=self.tile,
                scale=self.scale,
            )
        )
        end = time.monotonic() + seconds
        while time.monotonic() < end and self._pump():
            self._clock.tick(30)
        return self.open

    def _show(self, frame: Image.Image) -> None:
        pg = self._pg
        if self._screen is None or self._screen.get_size() != frame.size:
            self._screen = pg.display.set_mode(frame.size)
        self._screen.blit(pg.image.frombytes(frame.tobytes(), frame.size, "RGB"), (0, 0))
        pg.display.flip()
        self.last_frame = frame

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
) -> int:
    """Play an episode file in a window, no backend needed; returns the frames shown.

    With ``verify`` the file is first re-stepped through the simulator
    (:func:`~gridworld.record.replay`), so what you watch is proven reproducible.
    """
    if verify:
        for _ in replay(path):
            pass
    episode = read_episode(path)
    shown = 0
    with LiveView(
        tile=tile, scale=scale, fps=fps, caption=f"gridworld — {Path(path).name}"
    ) as view:
        for t in episode.ticks:
            if not view.update(t.observation, t.probabilities, t.action, t.oracle_action, t.timing):
                return shown
            shown += 1
        if episode.end is not None and view.update(episode.end.observation):
            shown += 1
        if hold:
            view.hold()
    return shown
