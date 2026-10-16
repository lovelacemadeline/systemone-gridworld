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

**Image mode** is not supported: the golden library has no vision port yet, so
a request with an image block raises :class:`NotImplementedError`.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .schema import uses_local_extensions

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

    def cache_prefix(self, tokens: Sequence[int]) -> Any:
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
    ) -> None:
        decide, CalibrationConfig, default_path, SystemOneRequest = _import()
        self._decide, self._request_cls = decide, SystemOneRequest
        if runner is None:
            from mlx_classifiers.mlx_runner import MLXRunner

            runner = MLXRunner.load(model, int8=int8)
        if calibration is None or isinstance(calibration, (str, Path)):
            calibration = CalibrationConfig.load_or_empty(calibration or default_path())
        self.calibration = calibration
        self.runner = _PrefixMemo(runner, prefix_cache_size)
        self.model_id: str = runner.model_id
        self.id = f"local:{self.model_id}" + (":int8" if int8 else "")

    def decide(self, request: dict[str, Any]) -> dict[str, Any]:
        if uses_local_extensions(request):
            raise NotImplementedError(
                "local backend: image mode is not supported yet (mlx-classifiers has no "
                "vision port); use mode 'text'"
            )
        req = self._request_cls.model_validate(request)
        temperature = self.calibration.temperature(self.model_id, req.effective_options.readout)
        return self._decide(req, self.runner, temperature=temperature).to_wire()
