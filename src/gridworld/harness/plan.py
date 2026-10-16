"""System Two plan calls (story 5.1): a short free-text plan from the same model.

A :class:`Planner` turns the rules prefix and the current rendered state into
a :class:`PlanResult`. The prompt is a chat with the prefix as the system turn
and the state plus :data:`PLAN_INSTRUCTION` as the user turn.

**Styles** (``--plan``): ``direct`` asks for the plan with thinking off;
``trace`` turns the model's thinking on, keeps the trace in the record, and
puts only the final plan in the memory tail. :func:`split_trace` separates
them: Gemma 4 writes ``<|channel>thought ... <channel|>`` then the answer;
``<think> ... </think>`` is also understood.

**Limits**: every call sets its own ``max_tokens`` (default 4096, never a chat
default) and records ``finish_reason``. A call that stops on the cap is
``truncated``; if it was cut inside the trace, the plan is empty — never a
half-thought passed off as a plan.

Implementations: :class:`LocalPlanner` (in-process on the LocalBackend's
loaded mlx-lm model, its own KV cache, the tokenizer's own chat template so the
thinking toggle is honoured), :class:`HTTPPlanner` (``POST
/v1/chat/completions`` with ``max_tokens`` and ``enable_thinking``), and
:class:`FakePlanner` for tests.
"""

from __future__ import annotations

import os
import time
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict

__all__ = [
    "DEFAULT_PLAN_MAX_TOKENS",
    "PLAN_INSTRUCTION",
    "FakePlanner",
    "HTTPPlanner",
    "LocalPlanner",
    "PlanResult",
    "PlanStyle",
    "Planner",
    "plan_messages",
    "split_trace",
]

PlanStyle = Literal["direct", "trace"]

DEFAULT_PLAN_MAX_TOKENS = 4096

PLAN_INSTRUCTION = (
    "Write a short plan: goal direction, route as a list of moves, threats to avoid. "
    "At most 80 words."
)

_MARKERS = (("<|channel>thought", "<channel|>"), ("<think>", "</think>"))


class PlanResult(BaseModel):
    """One plan call, as recorded on the tick that made it."""

    model_config = ConfigDict(frozen=True)

    plan: str
    trace: str | None = None
    style: PlanStyle
    completion_tokens: int
    prompt_tokens: int | None = None
    finish_reason: str
    truncated: bool
    wall_ms: float
    planner: str


class Planner(Protocol):
    id: str

    def plan(
        self, prefix: str, state_text: str, *, style: PlanStyle, max_tokens: int
    ) -> PlanResult: ...


def plan_messages(prefix: str, state_text: str) -> list[dict[str, str]]:
    """The chat: rules prefix as system, state plus the plan instruction as user."""
    return [
        {"role": "system", "content": prefix},
        {"role": "user", "content": f"{state_text}\n\n{PLAN_INSTRUCTION}"},
    ]


def split_trace(text: str) -> tuple[str | None, str, bool]:
    """``(trace, plan, closed)``: the thinking trace (if any), the answer, and whether
    an opened trace was closed (``False`` means generation stopped mid-thought)."""
    stripped = text.lstrip()
    for start, end in _MARKERS:
        if stripped.startswith(start):
            body = stripped[len(start) :]
            if end not in body:
                return body.strip(), "", False
            trace, plan = body.split(end, 1)
            return trace.strip(), plan.strip(), True
    return None, text.strip(), True


def _result(
    text: str,
    *,
    style: PlanStyle,
    completion_tokens: int,
    prompt_tokens: int | None,
    finish_reason: str,
    wall_ms: float,
    planner: str,
) -> PlanResult:
    trace, plan, closed = split_trace(text)
    truncated = finish_reason == "length" or not closed
    return PlanResult(
        plan=plan,
        trace=trace,
        style=style,
        completion_tokens=completion_tokens,
        prompt_tokens=prompt_tokens,
        finish_reason=finish_reason,
        truncated=truncated,
        wall_ms=wall_ms,
        planner=planner,
    )


class FakePlanner:
    """Scripted plans for tests: returns ``text`` (optionally with a trace), counting calls."""

    def __init__(
        self,
        text: str = "Head for G along the shortest open path; fight only when cornered.",
        *,
        trace: str = "The goal is somewhere on the map; I should move toward it.",
        tokens: int = 40,
        truncated: bool = False,
        latency_s: float = 0.0,
    ) -> None:
        self.text, self.trace, self.tokens = text, trace, tokens
        self.truncated, self.latency_s = truncated, latency_s
        self.calls: list[dict[str, Any]] = []
        self.id = "fake-planner"

    def plan(
        self, prefix: str, state_text: str, *, style: PlanStyle, max_tokens: int
    ) -> PlanResult:
        self.calls.append({"prefix": prefix, "state": state_text, "style": style})
        if self.latency_s:
            time.sleep(self.latency_s)
        if style == "trace":
            raw = f"<|channel>thought\n{self.trace}" + (
                "" if self.truncated else f"<channel|>{self.text}"
            )
        else:
            raw = self.text
        return _result(
            raw,
            style=style,
            completion_tokens=max_tokens if self.truncated else self.tokens,
            prompt_tokens=len(prefix + state_text) // 4,
            finish_reason="length" if self.truncated else "stop",
            wall_ms=self.latency_s * 1000,
            planner=self.id,
        )


class LocalPlanner:
    """In-process plans on an mlx-lm ``(model, tokenizer)``; greedy, fresh KV cache per call."""

    def __init__(self, model: Any, tokenizer: Any, model_id: str = "local") -> None:
        self.model, self.tokenizer = model, tokenizer
        self.id = f"local-plan:{model_id}"

    @classmethod
    def from_backend(cls, backend: Any) -> LocalPlanner:
        """Share the weights a :class:`~gridworld.backends.local.LocalBackend` loaded."""
        runner = getattr(backend.runner, "runner", backend.runner)  # unwrap the prefix memo
        return cls(runner.model, runner.tokenizer, backend.model_id)

    def plan(
        self, prefix: str, state_text: str, *, style: PlanStyle, max_tokens: int
    ) -> PlanResult:
        from mlx_lm.generate import stream_generate

        prompt = self.tokenizer.apply_chat_template(
            plan_messages(prefix, state_text),
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=style == "trace",
        )
        t0 = time.perf_counter()
        pieces, last = [], None
        for last in stream_generate(self.model, self.tokenizer, prompt, max_tokens=max_tokens):
            pieces.append(last.text)
        wall_ms = (time.perf_counter() - t0) * 1000
        return _result(
            "".join(pieces),
            style=style,
            completion_tokens=last.generation_tokens if last else 0,
            prompt_tokens=last.prompt_tokens if last else None,
            finish_reason=(last.finish_reason if last else None) or "length",
            wall_ms=wall_ms,
            planner=self.id,
        )


class HTTPPlanner:
    """``POST {base_url}/v1/chat/completions`` with ``max_tokens`` and ``enable_thinking``.

    Accepts the trace either inline (think markers in ``content``) or as a
    separate ``reasoning_content`` field on the message.
    """

    ROUTE = "/v1/chat/completions"

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8080",
        *,
        token_env: str = "SYSTEMONE_API_KEY",
        timeout: float = 600.0,
        client: Any = None,
    ) -> None:
        import httpx

        if client is None:
            client = httpx.Client(
                base_url=base_url, timeout=timeout, transport=httpx.HTTPTransport(retries=0)
            )
        token = os.environ.get(token_env) if token_env else None
        if token:
            client.headers["Authorization"] = f"Bearer {token}"
        self.client = client
        self.id = f"http-plan:{base_url}"

    def plan(
        self, prefix: str, state_text: str, *, style: PlanStyle, max_tokens: int
    ) -> PlanResult:
        body = {
            "messages": plan_messages(prefix, state_text),
            "max_tokens": max_tokens,
            "temperature": 0.0,
            "enable_thinking": style == "trace",
        }
        t0 = time.perf_counter()
        reply = self.client.post(self.ROUTE, json=body)
        wall_ms = (time.perf_counter() - t0) * 1000
        reply.raise_for_status()
        data = reply.json()
        choice = data["choices"][0]
        message = choice["message"]
        text = message.get("content") or ""
        if message.get("reasoning_content"):
            text = f"<think>{message['reasoning_content']}</think>{text}"
        usage = data.get("usage", {})
        return _result(
            text,
            style=style,
            completion_tokens=int(usage.get("completion_tokens", 0)),
            prompt_tokens=usage.get("prompt_tokens"),
            finish_reason=choice.get("finish_reason") or "length",
            wall_ms=wall_ms,
            planner=self.id,
        )
