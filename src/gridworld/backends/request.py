"""Request builder (story 3.1): one observation becomes one v1 ``SystemOneRequest`` dict.

Shape::

    {"prefix": <caller's stable rules text>,
     "state": <state text>                                         # mode "text"
           | [IMAGE_KEY, {"type": "image/png", "base64": <PNG>}, <state text>],  # "image"
     "questions": {"action": {"type": "choice", "instructions": "Which action next?",
                              "criteria": {<the six actions, in Action order>: <one line>}}}}

The state text is :func:`~gridworld.render.text.to_text` of the observation,
with ``memory_tail`` appended to its status line as `` | <tail>`` when given
(story 4.4's ``summary`` mode, and the System Two plan seam). The status line
stays the last line, so the stable-first layout (story 2.1) still maximises
the shared prefix between ticks and only the status line differs from
``none``.

**Image mode** (story 3.5; image blocks are v1 schema since golden 0e0fe18)
sends :data:`IMAGE_KEY` (one stable sentence saying what the colours mean),
the :func:`~gridworld.render.image.to_png` frame, then the same state text.
``image_only=True`` drops the rendered text view: the state is the key and
the frame, plus the memory tail as its own text block when there is one (so
summary memory is held constant between the two image variants).
:attr:`BuiltRequest.frame_sha256` is the sha256 of the PNG bytes sent.

Story 5.7's ``--think action`` passes ``plan_option=True``: the action
question's criteria gain a seventh option, :data:`PLAN_OPTION` (``plan``),
after ``wait``, whatever the legal mask offers. It is not an action;
:func:`~gridworld.backends.adapter.call` reads it as a request to plan.

Story 4.4's ``transcript`` mode passes ``history`` (prior turns): the state
is then :func:`build_state` of ``[*history, text]``, a list of strings —
valid under the vendored schema. In image mode the history goes between the
key and the current frame, and may itself hold image blocks (story 4.7's
frame transcript: ``[frame, "answer: east", frame, ...]``), so earlier frames
stay a stable token prefix from tick to tick.
"""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from typing import Any, Literal

from ..render.text import to_text
from ..sim import Action, Observation, legal_actions
from .schema import IMAGE_BLOCK_TYPE

__all__ = [
    "ACTION_CRITERIA",
    "DEFAULT_PREFIX",
    "IMAGE_KEY",
    "PLAN_CRITERION",
    "PLAN_OPTION",
    "QUESTION",
    "BuiltRequest",
    "Mode",
    "build_request",
    "build_state",
    "image_block",
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

#: Story 5.7: the seventh option of the action question under ``--think action``.
PLAN_OPTION = "plan"
PLAN_CRITERION = (
    "Pause to make a plan before acting (costs nothing in game time unless --think-cost tick)."
)

DEFAULT_PREFIX = (
    "You are playing a turn-based grid game. Each turn you see the map and a status line, "
    "and you choose exactly one action. Reach the goal G without dying; monsters M that "
    "are next to you hit you every turn."
)

#: Story 3.5: what the frame's colours mean (the golden library's gridworld image
#: battery uses the same sentence). Stable across ticks, so it is cached prefix.
IMAGE_KEY = (
    "The picture is the map, north up: you are the blue square, the goal is the green "
    "cell, monsters are red cells (white pips are their hp), walls are dark grey and "
    "floor is light. The dark strip under the map shows your hp, the tick and your last "
    "action."
)


@dataclass(frozen=True)
class BuiltRequest:
    """The wire request plus this tick's state text (for token accounting and transcripts)."""

    request: dict[str, Any]
    text: str
    mode: Mode
    offered: tuple[Action, ...] = tuple(Action)
    #: Story 3.5: sha256 (hex) of the PNG frame sent in image mode, else None.
    frame_sha256: str | None = None


def image_block(png: bytes) -> dict[str, str]:
    """A v1 image block for ``png``."""
    return {"type": IMAGE_BLOCK_TYPE, "base64": base64.b64encode(png).decode("ascii")}


def build_state(turns: list[Any], png: bytes | None = None) -> str | list[Any]:
    """The ``state`` field: a lone text turn as a string, else a list (image block last)."""
    if png is None and len(turns) == 1 and isinstance(turns[0], str):
        return turns[0]
    blocks: list[Any] = list(turns)
    if png is not None:
        blocks.append(image_block(png))
    return blocks


def build_request(
    obs: Observation,
    *,
    mode: Mode = "text",
    prefix: str = DEFAULT_PREFIX,
    memory_tail: str | None = None,
    history: list[Any] | tuple[Any, ...] = (),
    model: str | None = None,
    options: dict[str, Any] | None = None,
    legal_only: bool = False,
    label_style: str | None = None,
    extra_questions: dict[str, Any] | None = None,
    plan_option: bool = False,
    tile: int = 16,
    image_only: bool = False,
) -> BuiltRequest:
    """Build the one-question ``choice`` request for ``obs`` in ``mode``.

    ``legal_only`` offers only :func:`~gridworld.sim.legal_actions` (story 4.5;
    off by default so the baseline sees all six). ``label_style`` sets
    ``options.label_style`` (v1 schema since golden 22f4d22); ``None`` or
    ``"letters"`` leaves it out, which is the upstream default.
    ``extra_questions`` are added after ``action`` (System Two's
    ``pause_to_plan`` noul, story 5.2). ``plan_option`` appends
    :data:`PLAN_OPTION` to the action criteria (story 5.7); ``offered`` stays
    the actions only. ``image_only`` (image mode only) drops the text view.
    """
    text = to_text(obs)
    if memory_tail:
        text = f"{text} | {memory_tail}"
    frame_sha256 = None
    if mode == "text":
        if image_only:
            raise ValueError("image_only needs mode 'image'")
        state = build_state([*history, text])
    elif mode == "image":
        from ..render.image import to_png

        png = to_png(obs, tile)
        frame_sha256 = hashlib.sha256(png).hexdigest()
        current: list[Any] = [image_block(png)]
        if not image_only:
            current.append(text)
        elif memory_tail:
            current.append(memory_tail)
        state = [IMAGE_KEY, *history, *current]
    else:
        raise ValueError(f"unknown mode {mode!r}; expected 'text' or 'image'")
    offered = legal_actions(obs) if legal_only else tuple(Action)
    criteria = {a.value: ACTION_CRITERIA[a.value] for a in offered}
    if plan_option:
        criteria[PLAN_OPTION] = PLAN_CRITERION
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
                "criteria": criteria,
            },
            **(extra_questions or {}),
        },
    }
    options = dict(options or {})
    if label_style not in (None, "letters"):
        options["label_style"] = label_style
    if options:
        request["options"] = options
    return BuiltRequest(
        request=request, text=text, mode=mode, offered=offered, frame_sha256=frame_sha256
    )
