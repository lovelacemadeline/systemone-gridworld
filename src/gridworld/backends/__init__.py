"""Backends behind the v1 wire schema (ADR-0002) and the validating adapter."""

from __future__ import annotations

from typing import Any

from .adapter import BackendError, Decision, call
from .base import Backend
from .request import BuiltRequest, build_request
from .schema import SchemaError, validate_request, validate_response

__all__ = [
    "BACKENDS",
    "Backend",
    "BackendError",
    "BuiltRequest",
    "Decision",
    "SchemaError",
    "build_request",
    "call",
    "make_backend",
    "validate_request",
    "validate_response",
]

#: name -> "module:Class", imported only when made (keeps optional extras optional).
BACKENDS: dict[str, str] = {
    "fake": ".fake:FakeBackend",
    "local": ".local:LocalBackend",
    "http": ".http:HTTPBackend",
}


def make_backend(name: str, **kwargs: Any) -> Backend:
    """Construct a registered backend by name (see :data:`BACKENDS`)."""
    from importlib import import_module

    try:
        target = BACKENDS[name]
    except KeyError:
        raise ValueError(f"unknown backend {name!r}; choose from {sorted(BACKENDS)}") from None
    module, cls = target.split(":")
    return getattr(import_module(module, __package__), cls)(**kwargs)
