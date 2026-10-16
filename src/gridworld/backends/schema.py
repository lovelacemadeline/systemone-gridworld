"""The vendored v1 wire schema (story 3.1, ADR-0002) and validation against it.

The two JSON Schemas under ``schema/`` are vendored byte-for-byte from the
golden repo (provenance in ``schema/VENDORED.txt``) and never edited. One local
extension exists, documented in ``schema/local-extensions.md``: an array
``state`` may also hold image blocks ``{"type": "image/png", "base64": ...}``.
It is applied to an in-memory copy of the request schema
(:func:`extended_request_schema`) and used only for requests that need it, so
a text-mode request is always checked against the unmodified upstream schema.

Every failure raises :class:`SchemaError`, whose message lists each violation
as ``<JSON path>: <message>`` (for an unknown field the path is its parent and
the message names the field).
"""

from __future__ import annotations

import copy
import json
from functools import cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

__all__ = [
    "IMAGE_BLOCK_TYPE",
    "SchemaError",
    "extended_request_schema",
    "load_schema",
    "uses_local_extensions",
    "validate_request",
    "validate_response",
]

IMAGE_BLOCK_TYPE = "image/png"

_IMAGE_BLOCK = {
    "type": "object",
    "required": ["type", "base64"],
    "additionalProperties": False,
    "properties": {
        "type": {"const": IMAGE_BLOCK_TYPE},
        "base64": {"type": "string", "contentEncoding": "base64"},
    },
}


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
def extended_request_schema() -> dict[str, Any]:
    """The request schema plus the image-block extension (schema/local-extensions.md)."""
    schema = copy.deepcopy(load_schema("request"))
    for branch in schema["properties"]["state"]["oneOf"]:
        if branch.get("type") == "array":
            branch["items"] = {"anyOf": [{"type": "string"}, _IMAGE_BLOCK]}
    schema["$id"] = schema["$id"].replace("request.json", "request.x-local-image.json")
    return schema


@cache
def _validator(name: str, extended: bool) -> Draft202012Validator:
    schema = extended_request_schema() if extended else load_schema(name)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def uses_local_extensions(request: dict[str, Any]) -> bool:
    """True when ``state`` is an array holding anything other than strings."""
    state = request.get("state")
    return isinstance(state, list) and any(not isinstance(s, str) for s in state)


def _check(which: str, validator: Draft202012Validator, doc: Any) -> None:
    errors = sorted(validator.iter_errors(doc), key=lambda e: (e.json_path, e.message))
    if errors:
        raise SchemaError(which, [(e.json_path, e.message) for e in errors])


def validate_request(request: dict[str, Any]) -> None:
    """Raise :class:`SchemaError` unless ``request`` is a valid v1 request.

    Requests carrying image blocks are checked against the locally extended
    schema; all others against the vendored one.
    """
    _check("request", _validator("request", uses_local_extensions(request)), request)


def validate_response(response: dict[str, Any]) -> None:
    """Raise :class:`SchemaError` unless ``response`` is a valid v1 response."""
    _check("response", _validator("response", False), response)
