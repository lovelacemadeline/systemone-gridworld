---
type: story
status: completed
title: Vendored schema, request builder and validating adapter protocol
owner: maddie
updated: 2026-10-16
anchor:
  - symbol: "src/gridworld/backends/schema.py::validate_request"
  - symbol: "src/gridworld/backends/schema.py::validate_response"
  - symbol: "src/gridworld/backends/schema.py::load_schema"
  - symbol: "src/gridworld/backends/request.py::build_request"
  - symbol: "src/gridworld/backends/base.py::Backend"
  - symbol: "src/gridworld/backends/adapter.py::call"
  - symbol: "src/gridworld/backends/__init__.py::make_backend"
  - test: "tests/test_backend_schema.py::test_text_request_shape_validates_against_the_vendored_schema"
  - test: "tests/test_backend_schema.py::test_image_request_carries_text_and_png_block"
  - test: "tests/test_backend_schema.py::test_extra_top_level_field_fails_naming_the_field"
  - test: "tests/test_backend_schema.py::test_request_errors_name_the_json_path"
  - test: "tests/test_backend_schema.py::test_schema_valid_but_wrong_answers_fail"
---

# Story 3.1 — Vendored schema, request builder and validating adapter protocol

Vendor `schema/systemone-{request,response}.schema.json` from the golden repo with the source commit in a README; `build_request(observation, mode, prefix)` producing a `choice` question over the six actions with the rendered state (text, or text plus base64 PNG block); a `Backend` protocol whose caller validates request and response against the schema.

## As built

- **Schema.** The two schemas are vendored unmodified; provenance (golden
  commit f878a9d) is in `schema/VENDORED.txt`. `backends/schema.py` validates
  with `jsonschema` (Draft 2020-12, now a core dependency) and raises
  `SchemaError` listing every violation as `<JSON path>: <message>`. The wheel
  ships `schema/` inside the package (hatch `force-include`).
- **Local extension — a schema proposal for the golden repo.** The vendored
  `state` array allows only strings, so an image block does not validate.
  `extended_request_schema()` adds `{"type": "image/png", "base64": ...}`
  items to an in-memory copy, documented in `schema/local-extensions.md`, and
  is used only for requests whose `state` array holds a non-string. Upstream
  should define image state; then re-vendor and drop the extension.
  *(Done in story 3.5: golden 0e0fe18 defines the block field for field, the
  schema was re-vendored at 316f7c5, and the extension and its doc are gone.)*
- **Request.** `build_request(obs, mode="text"|"image", prefix=..., memory_tail=None)`
  returns a `BuiltRequest(request, text, mode)`: `prefix` is the caller's
  stable rules text (default `DEFAULT_PREFIX`), `state` is `to_text(obs)` (plus
  `memory_tail` on the last line, room for story 4.4's summary mode) or, in
  image mode, `[text, png_block]`. One `choice` question `action`, "Which action
  next?", criteria the six actions in `Action` order with one-line
  descriptions. `build_state` takes a list of text turns, so story 4.4's
  transcript mode is a longer list of strings, valid under the vendored
  schema. `text` is returned for token accounting.
- **Protocol and adapter.** `Backend` is a runtime-checkable protocol (`id`,
  `decide(dict) -> dict`). `adapter.call(backend, request)` validates the
  request, calls the backend on a deep copy, times it, validates the response,
  then checks what the schema cannot (the `action` answer exists, is a
  choice, picks a real action, covers all six probabilities), raising
  `BackendError`. It returns a `Decision` (action, probabilities, confidence,
  usage, backend-reported timing, wall ms, raw response).
- `backends/__init__.py::make_backend(name, **kw)` builds registered backends
  by name with lazy imports, so optional extras stay optional.

## Acceptance Criteria
- **Given** a backend that returns an extra top-level field **when** called through the adapter **then** validation fails naming the field.
- **Given** an image-mode request **when** validated **then** it passes only through the documented local extension.
