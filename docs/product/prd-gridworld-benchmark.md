---
type: prd
status: active
title: Gridworld benchmark for System One decision backends
owner: maddie
updated: 2026-10-16
---

# PRD — Gridworld benchmark

## Problem

The static battery in mlx-lm-as-classifiers answers "is a single decision
sensible". It cannot answer the questions a robot or game controller cares
about: how many decisions per second end to end, how the model behaves over a
*sequence* of changing states, and whether a text observation and an image of
the same state lead to the same decisions. Those need a loop.

## What we build

A deterministic gridworld with a small API (reset, step, observe) whose
observation is one structured record. Three consumers derive from it:

1. **Text renderer**: the observation as prompt text, stable parts first
   (rules, legend, map), volatile line last (hp, adjacent threats, last action).
2. **Image renderer**: the same observation as a small PNG for vision
   endpoints. Lossless with respect to the text view (ADR-0001).
3. **Live view**: a pygame window showing the map, the backend's probability
   bars over the six actions, the oracle's pick, and running decisions/s, so a
   human can watch the model play in real time.

Backends plug in behind one adapter that speaks only the `/v1/systemone` wire
schema (ADR-0002): the golden library in-process, its server over HTTP, a
hosted Jev-style API, and later the Swift port. Each tick the harness asks one
`choice` question over north, south, east, west, attack, wait; feeds the
answer back; logs probabilities and timing.

A scripted oracle (shortest path to goal, attack when adjacent, wait when
nothing better) scores agreement rate, episode completion, and steps versus
oracle without any labelling. Episodes record to JSONL so they replay in the
live view without re-running a model.

## Non-goals

- Roguelike depth (keys, doors, inventory) in the first version.
- Training anything. Backends are black boxes behind the schema.
- Owning the schema. It is pinned from the golden repo by URL.

## Success criteria

- Headless episodes run in CI with a fake backend; the live view is optional.
- Text and image observations of the same state carry the same information
  (a test renders both from one observation and checks the image decodes back
  to the same grid).
- A report per run: agreement, completion, steps/oracle-steps, decisions/s,
  p50/p95 latency, tokens per observation, with backend id and git rev.

## Epics

See [epic registry](../epics/index.md).
