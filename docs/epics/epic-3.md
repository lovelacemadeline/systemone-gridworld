---
type: epic
status: completed
title: Backends behind the wire schema
epic: 3
owner: maddie
updated: 2026-10-16
---

# Epic 3 — Backends behind the wire schema

One adapter protocol: request dict in, response dict out, validated both ways against the vendored v1 schema (ADR-0002). Backends: a fake (oracle plus noise, for CI), the golden library in-process, its HTTP server, and a generic HTTP backend for Jev-shaped hosted APIs.

## Stories
| id | title | status |
|---|---|---|
| 3.1 | Vendored schema, request builder and validating adapter protocol | completed |
| 3.2 | Fake backend — oracle with controllable noise | completed |
| 3.3 | In-process backend over mlx-classifiers decide() | completed |
| 3.4 | HTTP backend for /v1/systemone servers | completed |
| 3.5 | Image mode through the local backend | completed |
## Related
- ADR-0002, [golden repo schema](https://github.com/lovelacemadeline/mlx-lm-as-classifiers/tree/main/schema)
