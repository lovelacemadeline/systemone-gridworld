"""The default rules prefix (story 4.1): stable text sent as the request ``prefix``.

It is identical on every tick, so a backend with prefix caching (the golden
server, :class:`~gridworld.backends.local.LocalBackend`) prefills it once.
``gridworld play --prefix FILE`` replaces it; :func:`load_prefix` reads that.

Under ``--think action`` (story 5.7) :func:`with_plan_option` appends
:data:`PLAN_OPTION_SENTENCE` to whichever prefix is in use; no other mode
changes the prefix.

Story 4.8: :class:`PrefixSource` holds the prefix for a session, either fixed
text or a file that is re-read whenever its mtime changes, with a version
counter and sha256. The loop calls :meth:`PrefixSource.current` at the start
of every tick, so an edit takes effect on the next tick (the backend's prefix
cache sees a new prefix; nothing in the harness is invalidated).
:func:`edit_prefix` is what the viewer's P key does.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

__all__ = [
    "DEFAULT_PREFIX",
    "PLAN_OPTION_SENTENCE",
    "PrefixSource",
    "edit_prefix",
    "load_prefix",
    "open_with_platform",
    "with_plan_option",
]

DEFAULT_PREFIX = """\
You are playing a turn-based grid game, one decision per turn.

Each turn you see a legend, the map, and one status line. On the map, @ is you, \
G is the goal, M is a monster, # is a wall and . is open floor. x grows to the right \
(east) and y grows downward (south), so north is y - 1.

Rules:
- Moving into a wall, the edge of the map, or a monster does nothing (the turn still passes).
- attack hits one monster next to you (not diagonal) for 1 damage; at 0 hp it is removed.
- At the end of every turn, each monster next to you hits you for 1. At 0 hp you lose.
- Monsters that can see you (within 4 steps) move one step toward you each turn.
- Reach G to win. You lose if you have not reached it in 200 turns.

Good play: head for the goal along the shortest safe path; fight a monster that is \
already next to you when you can win the exchange; avoid stepping next to monsters \
when there is another way.

Answer with exactly one action."""


def load_prefix(path: str | Path | None) -> str:
    """The prefix text: the file at ``path`` (trailing whitespace stripped) or the default."""
    if path is None:
        return DEFAULT_PREFIX
    return Path(path).read_text(encoding="utf-8").rstrip()


PLAN_OPTION_SENTENCE = (
    "You may also answer plan to pause and make a short plan first; you then choose "
    "your action with the plan in view."
)


def with_plan_option(prefix: str) -> str:
    """``prefix`` plus the sentence describing the ``plan`` option (``--think action``)."""
    return f"{prefix}\n\n{PLAN_OPTION_SENTENCE}"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class PrefixSource:
    """The rules prefix: fixed text (``kind`` ``default``) or a hot-reloaded file.

    :meth:`current` returns the text, re-reading the file when its mtime
    changes; :attr:`version` (from 1) goes up each time the text actually
    changes, and :attr:`versions` lists every version loaded, with its
    sha256, length and source. A file that cannot be read (an editor
    mid-save) keeps the previous text and is retried on the next call.
    """

    def __init__(self, text: str | None = None, path: str | Path | None = None) -> None:
        if (text is None) == (path is None):
            raise ValueError("PrefixSource needs exactly one of text or path")
        self.path: Path | None = None
        self.text = "" if text is None else text
        self.version = 0
        self.versions: list[dict[str, Any]] = []
        self._mtime: int | None = None
        if path is None:
            self._accept(self.text)
        else:
            self.path = Path(path)
            self.path.stat()  # a missing --prefix file is an error at start, not later
            self.current()

    @classmethod
    def from_file(cls, path: str | Path) -> PrefixSource:
        return cls(path=path)

    @property
    def kind(self) -> str:
        return "default" if self.path is None else "file"

    @property
    def sha256(self) -> str:
        return _sha(self.text)

    def _accept(self, text: str) -> None:
        if self.version and text == self.text:
            return
        self.text = text
        self.version += 1
        self.versions.append(
            {
                "version": self.version,
                "sha256": self.sha256,
                "chars": len(text),
                "source": str(self.path) if self.path is not None else "default",
            }
        )

    def current(self) -> str:
        """The prefix text now (re-read if the file's mtime changed)."""
        if self.path is None:
            return self.text
        try:
            mtime = self.path.stat().st_mtime_ns
            if mtime != self._mtime:
                text = self.path.read_text(encoding="utf-8").rstrip()
                self._mtime = mtime
                self._accept(text)
        except OSError:
            pass
        return self.text

    def switch_to(self, path: str | Path) -> None:
        """Follow ``path`` from now on (the version goes up only if its text differs)."""
        self.path, self._mtime = Path(path), None
        self.current()


def open_with_platform(path: str | Path) -> None:
    """Open ``path`` with the platform opener (``open`` on macOS, else ``xdg-open``)."""
    cmd = "open" if sys.platform == "darwin" else "xdg-open"
    subprocess.Popen([cmd, str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def edit_prefix(
    source: PrefixSource,
    session_dir: str | Path,
    opener: Callable[[Path], None] | None = None,
) -> Path:
    """The viewer's P key: open the prefix file for editing.

    A file-backed source opens its own file. Otherwise the current text is
    written to ``<session_dir>/prefix.txt`` (only if that file does not exist
    yet), ``source`` switches to it, and it is opened. Returns the file.
    """
    if source.path is None:
        path = Path(session_dir) / "prefix.txt"
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(source.text + "\n", encoding="utf-8")
        source.switch_to(path)
    assert source.path is not None
    (opener or open_with_platform)(source.path)
    return source.path
