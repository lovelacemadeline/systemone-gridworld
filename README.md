---
type: guide
status: active
title: systemone-gridworld — README
owner: maddie
updated: 2026-10-16
---

# systemone-gridworld

A small deterministic gridworld for benchmarking "System One" decision
backends (typed, calibrated decisions over a declared option set, one forward
pass, no decoding) in a sequential loop. One simulator, one observation, three
consumers: a text renderer for text endpoints, an image renderer for vision
endpoints, and a live pygame window so you can watch a model play. A scripted
oracle scores agreement without labelling. Backends speak only a Jev-style
`/v1/systemone` wire schema (vendored under `schema/`), so any decision model
can be plugged in and compared.

What's measured per run: completion, oracle agreement, steps versus oracle,
oscillation (distinct cells per step, reversals), decisions per second with
p50/p95 latency, tokens per observation, and, when planning is on, how often
and why the model chose to think.

## Quick start

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/lovelacemadeline/systemone-gridworld
cd systemone-gridworld
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e '.[image,view,http,dev]'

# watch the scripted oracle play a map
.venv/bin/gridworld oracle --seed 3 --out runs/ep3.jsonl
.venv/bin/gridworld view runs/ep3.jsonl --fps 4

# run the benchmark loop against the fake backend (oracle plus noise)
.venv/bin/gridworld play --backend fake --noise 0.3 --episodes 5 --seed 0 --view
```

Esc or q closes the window; `--episodes 0` runs forever and writes a session
report under `runs/` on exit. Map flags: `--width`, `--height`, `--monsters`,
`--walls`, `--hp`, `--tick-limit`.

## Backends

- `--backend fake`: the oracle with controllable noise, for CI and plumbing.
- `--backend http --url http://host:port`: any server exposing
  `POST /v1/systemone` with the vendored schema (see `schema/`).
- `--backend local`: in-process over the `mlx-classifiers` library on Apple
  silicon. That library is not yet public; the HTTP backend is the way to
  plug in your own model in the meantime.

## Options that change what the model is asked

- `--labels letters|words`: answer tokens are A–F, or the action names.
- `--legal-only`: offer only moves that are legal from the current cell.
- `--memory none|summary|transcript`: what the model sees of its own history.
- `--think never|start|demand|rule|action` with `--plan direct|trace`:
  System Two planning, including `plan` as a seventh action the model can
  choose. `--think-cost free|tick` decides whether thinking costs a turn.
- `--damage-first`: stepping onto the goal beside a monster takes the hit
  first (default: reaching the goal ends the turn).

Everything is recorded per tick to JSONL and replays in the viewer with the
probability bars, plans, and planning ticks. Results from Gemma 4 E2B and the
26B MoE on Apple silicon are in `docs/stories/5-4-report.md` and the stories
around it; they are honest and include the failure modes.

Docs follow [`docs/doc-conventions.md`](docs/doc-conventions.md) and are
checked by `docloom check`. Start at
[`docs/product/prd-gridworld-benchmark.md`](docs/product/prd-gridworld-benchmark.md).
Licence: MIT.
