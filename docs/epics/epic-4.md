---
type: epic
status: completed
title: Harness, scoring and reports
epic: 4
owner: maddie
updated: 2026-10-17
---

# Epic 4 — Harness, scoring and reports

The loop: observe, render, ask one `choice`, act, log. Scoring: oracle agreement, completion rate, steps versus oracle steps, decisions/s end to end, p50/p95 latency, tokens per observation. A `gridworld play` CLI with `--backend`, `--mode text|image`, `--view`, `--episodes`, `--seed`, writing markdown and JSON under `runs/` with backend id, mode, git rev and power state.

## Stories
| id | title | status |
|---|---|---|
| 4.1 | Episode loop and decision log | completed |
| 4.2 | Scoring and the run report | completed |
| 4.3 | play CLI and headless CI run with the fake backend | completed |
| 4.4 | Memory modes — none, summary, transcript | completed |
| 4.5 | Legal-action mask and label style | completed |
| 4.6 | Summary memory knobs — recent-action length and visit counts | completed |
| 4.7 | Frame history as a transcript — past frames stay cached | completed |
| 4.8 | Edit the rules prefix live — hot reload and an edit key | completed |
| 4.9 | Stuck rule and a skip key | completed |
| 4.10 | Stuck means no new cell — the rule fires on pacing and parking | completed |
## Related
- [PRD](../product/prd-gridworld-benchmark.md)
