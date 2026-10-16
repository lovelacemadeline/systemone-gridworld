"""Story 3.1 — vendored schema, request builder and the validating adapter."""

from __future__ import annotations

import base64
import io

import pytest
from PIL import Image

from gridworld.backends import BackendError, SchemaError, build_request, call
from gridworld.backends.base import Backend
from gridworld.backends.request import ACTION_CRITERIA, DEFAULT_PREFIX, build_state
from gridworld.backends.schema import (
    extended_request_schema,
    load_schema,
    validate_request,
    validate_response,
)
from gridworld.render.image import to_image
from gridworld.render.text import to_text
from gridworld.sim import Action, generate_map

OBS = generate_map(3)


def good_response(choice="east", **extra):
    probs = {a.value: (0.5 if a.value == choice else 0.1) for a in Action}
    return {
        "model": "stub",
        "answers": {
            "action": {
                "type": "choice",
                "choice": choice,
                "probabilities": probs,
                "confidence": 0.5,
            }
        },
        "usage": {"input_tokens": 10, "output_tokens": 0},
        **extra,
    }


class Stub:
    id = "stub"

    def __init__(self, response):
        self.response = response
        self.seen = None

    def decide(self, request):
        self.seen = request
        request["state"] = "mutated"
        return self.response


def test_vendored_schemas_load_unmodified():
    assert load_schema("request")["title"] == "SystemOneRequest"
    assert load_schema("response")["title"] == "SystemOneResponse"
    assert extended_request_schema() != load_schema("request")
    assert load_schema("request")["properties"]["state"]["oneOf"][2]["items"] == {"type": "string"}


def test_text_request_shape_validates_against_the_vendored_schema():
    built = build_request(OBS, prefix="rules")
    req = built.request
    validate_request(req)
    assert req["prefix"] == "rules" and req["state"] == to_text(OBS) == built.text
    q = req["questions"]["action"]
    assert q["type"] == "choice" and q["instructions"] == "Which action next?"
    assert list(q["criteria"]) == [a.value for a in Action] == list(ACTION_CRITERIA)


def test_image_request_carries_text_and_png_block():
    built = build_request(OBS, mode="image")
    text, block = built.request["state"]
    assert text == built.text and block["type"] == "image/png"
    png = Image.open(io.BytesIO(base64.b64decode(block["base64"])))
    assert png.convert("RGB").tobytes() == to_image(OBS).tobytes()
    validate_request(built.request)  # passes only via the local extension


def test_image_block_fails_the_vendored_schema_alone():
    from jsonschema import Draft202012Validator

    built = build_request(OBS, mode="image")
    assert not Draft202012Validator(load_schema("request")).is_valid(built.request)


def test_memory_tail_goes_after_the_status_line():
    built = build_request(OBS, memory_tail="Recent: east, east, north")
    assert built.text.split("\n")[-2].startswith("Status:")
    assert built.request["state"].endswith("Recent: east, east, north")


def test_multi_turn_state_is_a_list_of_strings():
    req = build_request(OBS).request | {"state": build_state(["turn 1", "turn 2"])}
    validate_request(req)


def test_default_prefix_and_unknown_mode():
    assert build_request(OBS).request["prefix"] == DEFAULT_PREFIX
    with pytest.raises(ValueError, match="mode"):
        build_request(OBS, mode="audio")


def test_request_errors_name_the_json_path():
    req = build_request(OBS).request
    req["questions"]["action"]["criteria"] = {"only": None}
    with pytest.raises(SchemaError, match=r"\$\.questions\.action"):
        validate_request(req)


def test_adapter_returns_parsed_decision_and_isolates_the_request():
    stub = Stub(good_response("west", timing_ms={"total": 3.0}))
    assert isinstance(stub, Backend)
    req = build_request(OBS).request
    d = call(stub, req)
    assert d.action is Action.WEST and d.probabilities[Action.WEST] == 0.5
    assert d.usage == {"input_tokens": 10, "output_tokens": 0}
    assert d.timing_ms == {"total": 3.0} and d.wall_ms >= 0 and d.backend == "stub"
    assert req["state"] == to_text(OBS)  # the backend mutated only its copy


def test_extra_top_level_field_fails_naming_the_field():
    with pytest.raises(SchemaError, match="'surprise' was unexpected") as exc:
        call(Stub(good_response(surprise=1)), build_request(OBS).request)
    assert exc.value.which == "response" and exc.value.errors[0][0] == "$"


def test_invalid_request_never_reaches_the_backend():
    stub = Stub(good_response())
    req = build_request(OBS).request | {"bogus": True}
    with pytest.raises(SchemaError, match="request"):
        call(stub, req)
    assert stub.seen is None


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda r: r["answers"].pop("action"), "no answer"),
        (lambda r: r["answers"]["action"].update(choice="jump"), "not one of"),
        (lambda r: r["answers"]["action"]["probabilities"].pop("wait"), "probabilities cover"),
    ],
)
def test_schema_valid_but_wrong_answers_fail(mutate, match):
    resp = good_response()
    mutate(resp)
    validate_response(resp)
    with pytest.raises(BackendError, match=match):
        call(Stub(resp), build_request(OBS).request)
