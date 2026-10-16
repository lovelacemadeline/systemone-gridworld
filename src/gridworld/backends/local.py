"""In-process backend (story 3.3): the golden library's ``decide()`` on an MLX runner.

Optional (the ``local`` extra): ``mlx_classifiers`` is imported when the
backend is constructed, and a missing install raises :class:`ImportError`
naming the extra. The request dict is validated into the library's own
``SystemOneRequest`` and the answer returned via ``SystemOneResponse.to_wire()``,
so this backend speaks exactly the wire schema like the others (ADR-0002).

**Prefix caching across ticks.** ``decide()`` KV-caches the request's
``prefix`` once per call; on its own every tick would re-prefill it. The
runner is wrapped so ``cache_prefix`` is memoised by token ids (a small LRU,
the in-process twin of the server's ``PrefixLRU``), so ticks that share the
prefix reuse its cache — visible as ``usage.cached_tokens``.

**Calibration.** ``calibration`` may be a ``CalibrationConfig`` or a path; by
default the library's default calibration file is used (as ``mlx-classifiers
serve`` does), so in-process and HTTP numbers are comparable.

**Image mode** (story 3.5): image blocks go to ``decide`` unchanged; the
golden library (Epic 6, 0e0fe18 on) compiles each into the model's soft-token
run and encodes it with the vision tower, loaded on the first image and
memoised per PNG sha256. The runner's own delta cache (``prompt_cache``) keys
on image hashes, so a frame transcript reuses the KV of every earlier frame.
The vendored response has no encoder field, so the tower time the runner logs
for this decision (``vision_encode_ms``) is added to the response as
``timing_ms.encoder`` (``timing_ms`` is open in v1); 0 when every image was
memoised, absent for text-only requests.

**Soft-token budget** (follow-up on story 3.5, golden story 6.7): ``vision_tokens``
(``play --vision-tokens 70|140|280``) loads the runner with that budget per image
(``MLXRunner.vision_soft_tokens``): a 160 x 192 frame becomes 63 / 120 / 270 soft
tokens from 567 / 1080 / 2430 encoder patches. None keeps the checkpoint's 280. The
backend id gains ``:vt<N>`` so run reports say which budget played.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .schema import has_image_blocks

__all__ = ["LocalBackend"]

DEFAULT_MODEL = "mlx-community/gemma-4-E2B-it-qat-4bit"


def _import():
    try:
        import mlx_classifiers  # noqa: F401
        from mlx_classifiers.decide import decide
        from mlx_classifiers.fitting import CalibrationConfig, default_calibration_path
        from mlx_classifiers.schema import SystemOneRequest
    except ImportError as exc:
        raise ImportError(
            "the local backend needs mlx-classifiers: pip install 'systemone-gridworld[local]'"
        ) from exc
    return decide, CalibrationConfig, default_calibration_path, SystemOneRequest


class _PrefixMemo:
    """Runner proxy whose ``cache_prefix`` is served from a small LRU keyed by token ids."""

    def __init__(self, runner: Any, capacity: int = 8) -> None:
        self.runner, self.capacity = runner, capacity
        self._entries: OrderedDict[tuple[int, ...], Any] = OrderedDict()
        self.hits = self.misses = 0

    def __getattr__(self, name: str) -> Any:
        return getattr(self.runner, name)

    def cache_prefix(self, tokens: Sequence[int], **kw: Any) -> Any:
        if kw.get("images"):  # keyed by token ids alone, so never memoise an image prefix
            return self.runner.cache_prefix(tokens, **kw)
        key = tuple(tokens)
        if key in self._entries:
            self.hits += 1
            self._entries.move_to_end(key)
            return self._entries[key]
        self.misses += 1
        cache = self.runner.cache_prefix(key)
        self._entries[key] = cache
        while len(self._entries) > self.capacity:
            self._entries.popitem(last=False)
        return cache


class LocalBackend:
    """``mlx_classifiers.decide`` in-process. Pass ``runner`` to skip loading weights."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        *,
        int8: bool = False,
        calibration: Any = None,
        runner: Any = None,
        prefix_cache_size: int = 8,
        vision_tokens: int | None = None,
    ) -> None:
        decide, CalibrationConfig, default_path, SystemOneRequest = _import()
        self._decide, self._request_cls = decide, SystemOneRequest
        if runner is None:
            from mlx_classifiers.mlx_runner import MLXRunner

            kw = {"vision_soft_tokens": vision_tokens} if vision_tokens is not None else {}
            runner = MLXRunner.load(model, int8=int8, **kw)
        elif vision_tokens is not None and getattr(runner, "image_tokens", None) is not None:
            from dataclasses import replace

            runner.image_tokens = replace(runner.image_tokens, max_soft_tokens=vision_tokens)
        if calibration is None or isinstance(calibration, (str, Path)):
            calibration = CalibrationConfig.load_or_empty(calibration or default_path())
        self.calibration = calibration
        self.runner = _PrefixMemo(runner, prefix_cache_size)
        self.model_id: str = runner.model_id
        self.vision_tokens = vision_tokens
        self.id = (
            f"local:{self.model_id}"
            + (":int8" if int8 else "")
            + (f":vt{vision_tokens}" if vision_tokens is not None else "")
        )

    def _label_style_supported(self) -> bool:
        from mlx_classifiers.schema import RequestOptions

        return "label_style" in RequestOptions.model_fields

    def decide(self, request: dict[str, Any]) -> dict[str, Any]:
        style = (request.get("options") or {}).get("label_style")
        if style is not None and not self._label_style_supported():
            raise NotImplementedError(
                f"local backend: options.label_style={style!r} needs an mlx-classifiers with "
                "label_style support (golden commit 22f4d22 or later); use --labels letters"
            )
        req = self._request_cls.model_validate(request)
        temperature = self.calibration.temperature(self.model_id, req.effective_options.readout)
        encodes = getattr(self.runner.runner, "vision_encode_ms", None)
        before = len(encodes) if encodes is not None else 0
        wire = self._decide(req, self.runner, temperature=temperature).to_wire()
        if has_image_blocks(request) and encodes is not None:
            wire.setdefault("timing_ms", {})["encoder"] = sum(encodes[before:])
        return wire
