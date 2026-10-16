"""The vendored v1 wire schema (story 3.1, ADR-0002) and validation against it.

The two JSON Schemas under ``schema/`` are vendored byte-for-byte from the
golden repo (provenance in ``schema/VENDORED.txt``) and never edited. Nothing
is extended locally: image blocks ``{"type": "image/png", "base64": ...}`` in
an array ``state`` are upstream since golden 0e0fe18 (story 3.5 retired the
in-memory extension this module used to apply).

Every failure raises :class:`SchemaError`, whose message lists each violation
as ``<JSON path>: <message>`` (for an unknown field the path is its parent and
the message names the field).
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

__all__ = [
    "IMAGE_BLOCK_TYPE",
    "SchemaError",
    "has_image_blocks",
    "load_schema",
    "validate_request",
    "validate_response",
]

IMAGE_BLOCK_TYPE = "image/png"


class SchemaError(ValueError):
    """A request or response does not match the wire schema."""

    def __init__(self, which: str, errors: list[tuple[str, str]]):
        self.which = which
        self.errors = errors
        lines = "\n".join(f"  {path}: {msg}" for path, msg in errors)
        super().__init__(f"{which} does not match the v1 wire schema:\n{lines}")


def _schema_dir() -> Path:
    here = Path(__file__).resolve()
    for candidate in (here.parents[1] / "schema", here.parents[3] / "schema"):
        if (candidate / "systemone-request.schema.json").exists():
            return candidate
    raise FileNotFoundError("vendored schema/ directory not found")


@cache
def load_schema(name: str) -> dict[str, Any]:
    """``"request"`` or ``"response"``: the vendored schema as a dict."""
    return json.loads((_schema_dir() / f"systemone-{name}.schema.json").read_text())


@cache
def _validator(name: str) -> Draft202012Validator:
    schema = load_schema(name)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def has_image_blocks(request: dict[str, Any]) -> bool:
    """True when ``state`` is an array holding anything other than strings."""
    state = request.get("state")
    return isinstance(state, list) and any(not isinstance(s, str) for s in state)


def _check(which: str, validator: Draft202012Validator, doc: Any) -> None:
    errors = sorted(validator.iter_errors(doc), key=lambda e: (e.json_path, e.message))
    if errors:
        raise SchemaError(which, [(e.json_path, e.message) for e in errors])


def validate_request(request: dict[str, Any]) -> None:
    """Raise :class:`SchemaError` unless ``request`` is a valid v1 request."""
    _check("request", _validator("request"), request)


def validate_response(response: dict[str, Any]) -> None:
    """Raise :class:`SchemaError` unless ``response`` is a valid v1 response."""
    _check("response", _validator("response"), response)
