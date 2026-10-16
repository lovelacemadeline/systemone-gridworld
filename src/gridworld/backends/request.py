"""Request builder (story 3.1): one observation becomes one v1 ``SystemOneRequest`` dict.

Shape::

    {"prefix": <caller's stable rules text>,
     "state": <state text>                                  # mode "text"
           | [<state text>, {"type": "image/png", "base64": <PNG>}],  # mode "image"
     "questions": {"action": {"type": "choice", "instructions": "Which action next?",
                              "criteria": {<the six actions, in Action order>: <one line>}}}}

The state text is :func:`~gridworld.render.text.to_text` of the observation,
with ``memory_tail`` appended to its status line as `` | <tail>`` when given
(story 4.4's ``summary`` mode, and the System Two plan seam). The status line
stays the last line, so the stable-first layout (story 2.1) still maximises
the shared prefix between ticks and only the status line differs from
``none``. Image mode
sends the same text plus the :func:`~gridworld.render.image.to_png` block
(a local schema extension, see ``schema/local-extensions.md``).

Story 4.4's ``transcript`` mode passes ``history`` (prior turns): the state
is then :func:`build_state` of ``[*history, text]``, a list of strings —
valid under the vendored schema.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any, Literal

from ..render.text import to_text
from ..sim import Action, Observation, legal_actions
from .schema import IMAGE_BLOCK_TYPE

__all__ = [
    "ACTION_CRITERIA",
    "DEFAULT_PREFIX",
    "QUESTION",
    "BuiltRequest",
    "Mode",
    "build_request",
    "build_state",
]

Mode = Literal["text", "image"]

QUESTION = "action"

ACTION_CRITERIA: dict[str, str] = {
    Action.NORTH.value: "Move up one cell (y - 1).",
    Action.SOUTH.value: "Move down one cell (y + 1).",
    Action.EAST.value: "Move right one cell (x + 1).",
    Action.WEST.value: "Move left one cell (x - 1).",
    Action.ATTACK.value: "Hit one adjacent monster for 1 damage.",
    Action.WAIT.value: "Stay in place for one tick.",
}

DEFAULT_PREFIX = (
    "You are playing a turn-based grid game. Each turn you see the map and a status line, "
    "and you choose exactly one action. Reach the goal G without dying; monsters M that "
    "are next to you hit you every turn."
)


@dataclass(frozen=True)
class BuiltRequest:
    """The wire request plus this tick's state text (for token accounting and transcripts)."""

    request: dict[str, Any]
    text: str
    mode: Mode
    offered: tuple[Action, ...] = tuple(Action)


def build_state(turns: list[str], png: bytes | None = None) -> str | list[Any]:
    """The ``state`` field: a lone text turn as a string, else a list (image block last)."""
    if png is None and len(turns) == 1:
        return turns[0]
    blocks: list[Any] = list(turns)
    if png is not None:
        blocks.append({"type": IMAGE_BLOCK_TYPE, "base64": base64.b64encode(png).decode("ascii")})
    return blocks


def build_request(
    obs: Observation,
    *,
    mode: Mode = "text",
    prefix: str = DEFAULT_PREFIX,
    memory_tail: str | None = None,
    history: list[str] | tuple[str, ...] = (),
    model: str | None = None,
    options: dict[str, Any] | None = None,
    legal_only: bool = False,
    label_style: str | None = None,
    tile: int = 16,
) -> BuiltRequest:
    """Build the one-question ``choice`` request for ``obs`` in ``mode``.

    ``legal_only`` offers only :func:`~gridworld.sim.legal_actions` (story 4.5;
    off by default so the baseline sees all six). ``label_style`` sets
    ``options.label_style`` (a pending-upstream local extension); ``None`` or
    ``"letters"`` leaves it out, which is the upstream default.
    """
    text = to_text(obs)
    if memory_tail:
        text = f"{text} | {memory_tail}"
    turns = [*history, text]
    if mode == "text":
        state = build_state(turns)
    elif mode == "image":
        from ..render.image import to_png

        state = build_state(turns, to_png(obs, tile))
    else:
        raise ValueError(f"unknown mode {mode!r}; expected 'text' or 'image'")
    offered = legal_actions(obs) if legal_only else tuple(Action)
    request: dict[str, Any] = {}
    if model is not None:
        request["model"] = model
    request |= {
        "state": state,
        "prefix": prefix,
        "questions": {
            QUESTION: {
                "type": "choice",
                "instructions": "Which action next?",
                "criteria": {a.value: ACTION_CRITERIA[a.value] for a in offered},
            }
        },
    }
    options = dict(options or {})
    if label_style not in (None, "letters"):
        options["label_style"] = label_style
    if options:
        request["options"] = options
    return BuiltRequest(request=request, text=text, mode=mode, offered=offered)
