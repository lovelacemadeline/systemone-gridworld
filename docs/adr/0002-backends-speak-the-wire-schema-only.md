---
type: decision
status: active
title: Backends are adapters that speak only the /v1/systemone wire schema
owner: maddie
updated: 2026-10-16
---

# ADR-0002 — Backends speak the wire schema only

## Status
Active.

## Context
The benchmark should run any decision backend: the golden library in-process,
its server, a hosted Jev-style API, the Swift port. Coupling to any one of
their internals would make the numbers non-comparable and the repo
non-portable.

## Decision
A backend is a class with one method: take a `SystemOneRequest`-shaped dict,
return a `SystemOneResponse`-shaped dict. The schema is pinned from
https://github.com/lovelacemadeline/mlx-lm-as-classifiers/tree/main/schema
(v1) and vendored as JSON under `schema/` with its source commit recorded.
The harness validates every request and response against it, so a backend
that drifts fails loudly. Image observations travel as a base64 PNG in the
state (a list of blocks, one text and one image), which is an additive x-local
convention until the golden repo's vision port defines its own.

## Consequences
- Adding a backend is one small file; no backend can see sim internals.
- The repo depends on the schema, not on the library (the in-process backend
  is an optional extra).

## Alternatives rejected
- **Import the golden library's Runner directly**: fast, but then Jev or the
  Swift port cannot be benchmarked on equal terms. Rejected.
