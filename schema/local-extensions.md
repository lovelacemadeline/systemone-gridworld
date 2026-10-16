---
type: reference
status: active
title: Local extensions to the vendored v1 wire schema
owner: maddie
updated: 2026-10-16
---

# Local extensions to the vendored v1 wire schema

The JSON Schemas beside this file are vendored unmodified (see `VENDORED.txt`).
This repo applies exactly one extension, in memory, in
`src/gridworld/backends/schema.py::extended_request_schema`. It is a proposal
for the golden repo, not a fork: once upstream defines image state, re-vendor
and delete this file.

## Image blocks in an array `state`

Upstream, an array `state` is `{"type": "array", "items": {"type": "string"}}`.
Extended, each item may also be an image block:

```json
{"type": "object", "required": ["type", "base64"], "additionalProperties": false,
 "properties": {"type": {"const": "image/png"},
                "base64": {"type": "string", "contentEncoding": "base64"}}}
```

Image-mode requests are `[<state text>, {"type": "image/png", "base64": "..."}]`
(ADR-0002).

## When the extended schema is used

Only for requests whose `state` array holds a non-string; every other
request, and every response, is checked against the vendored schema as-is.
(`options.label_style`, a second extension during story 4.5, is upstream since
golden commit 22f4d22 and was removed here on re-vendoring.)
