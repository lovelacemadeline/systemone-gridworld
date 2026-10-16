---
type: guide
status: active
title: systemone-gridworld — README
owner: maddie
updated: 2026-10-16
---

# systemone-gridworld

A small deterministic gridworld for benchmarking System One decision backends
(typed, calibrated decisions over a declared option set) in a sequential loop.
One simulator, one observation, three consumers: a text renderer for text
endpoints, an image renderer for vision endpoints, and a live window for a
human watching the model play. A scripted oracle scores agreement without
labelling. Backends speak only the `/v1/systemone` wire schema from
[mlx-lm-as-classifiers](https://github.com/lovelacemadeline/mlx-lm-as-classifiers).

Docs follow [`docs/doc-conventions.md`](docs/doc-conventions.md); start at
[`docs/product/prd-gridworld-benchmark.md`](docs/product/prd-gridworld-benchmark.md).
