---
type: reference
status: active
title: Local extensions to the vendored v1 wire schema
owner: maddie
updated: 2026-10-16
---

# Local extensions to the vendored v1 wire schema

The JSON Schemas beside this file are vendored unmodified (see `VENDORED.txt`).
This repo applies two extensions, in memory, in
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

## `options.label_style` (pending upstream)

Upstream `RequestOptions` is closed. Extended, it also allows:

```json
"label_style": {"type": "string", "enum": ["letters", "option-text"], "default": "letters"}
```

`letters` labels options A., B., ...; `option-text` makes the option names
themselves the first-token labels. The golden repo is adding this option;
once it lands, re-vendor and drop this section (story 4.5). Until then the
in-process backend refuses it with a clear error unless the installed
mlx-classifiers knows the field. `gridworld play --labels letters` omits the
key entirely (the upstream default), so letters requests stay on the vendored
schema.

## When the extended schema is used

Only for requests whose `state` array holds a non-string or whose `options`
set `label_style`; every other request, and every response, is checked
against the vendored schema as-is.
