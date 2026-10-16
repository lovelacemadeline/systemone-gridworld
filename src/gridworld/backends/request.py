"""Request builder (story 3.1): one observation becomes one v1 ``SystemOneRequest`` dict.

Shape::

    {"prefix": <caller's stable rules text>,
     "state": <state text>                                  # mode "text"
           | [<state text>, {"type": "image/png", "base64": <PNG>}],  # mode "image"
     "questions": {"action": {"type": "choice", "instructions": "Which action next?",
                              "criteria": {<the six actions, in Action order>: <one line>}}}}

The state text is :func:`~gridworld.render.text.to_text` of the observation,
followed by ``memory_tail`` on its own line(s) when given (story 4.4's
``summary`` mode). It stays the last thing in the text so the stable-first
layout (story 2.1) still maximises the shared prefix between ticks. Image mode
sends the same text plus the :func:`~gridworld.render.image.to_png` block
(a local schema extension, see ``schema/local-extensions.md``).

Room left for story 4.4's ``transcript`` mode: the state is assembled by
:func:`build_state` from a list of text turns, so a multi-turn request is a
longer list of strings — already valid under the vendored schema.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any, Literal

from ..render.text import to_text
from ..sim import Action, Observation
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
    """The wire request plus the state text it carries (for token accounting)."""

    request: dict[str, Any]
    text: str
    mode: Mode


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
    model: str | None = None,
    options: dict[str, Any] | None = None,
    tile: int = 16,
) -> BuiltRequest:
    """Build the one-question ``choice`` request for ``obs`` in ``mode``."""
    text = to_text(obs)
    if memory_tail:
        text = f"{text}\n{memory_tail}"
    if mode == "text":
        state = build_state([text])
    elif mode == "image":
        from ..render.image import to_png

        state = build_state([text], to_png(obs, tile))
    else:
        raise ValueError(f"unknown mode {mode!r}; expected 'text' or 'image'")
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
                "criteria": dict(ACTION_CRITERIA),
            }
        },
    }
    if options:
        request["options"] = dict(options)
    return BuiltRequest(request=request, text=text, mode=mode)
