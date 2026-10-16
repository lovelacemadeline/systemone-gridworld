---
type: epic
status: completed
title: System Two — let the model choose to pause and plan
epic: 5
owner: maddie
updated: 2026-10-16
---

# Epic 5 — System Two

A planning mode on top of the decision loop. The same model that makes the
fast typed decisions also serves chat completions from the same process
(golden repo, Epic 3), so "thinking" is a call to the chat route with the
rendered state, producing a short free-text plan that is fed back into the
memory tail (story 4.4) for subsequent ticks. Three triggers, compared side
by side: never (baseline), once at episode start, and on demand, where each
tick carries a second `noul` question "pause to plan?" and a yes above a
threshold triggers a plan. The viewer shows the current plan text and marks
planning ticks on the timeline, so a human can see when it chose to think.
Cost is the point: a plan is hundreds of decoded tokens, so the report must
show agreement and completion against decisions per second and total tokens.

## Stories
| id | title | status |
|---|---|---|
| 5.1 | Plan call over the chat route and plan injection into the memory tail | completed |
| 5.2 | Triggers — never, at start, on demand via a second noul question | completed |
| 5.3 | Viewer plan panel and planning-tick markers | completed |
| 5.4 | Report — quality versus cost across triggers | completed |
| 5.5 | Planner on a different model than the decider | completed |

## Related
- Story 4.4 memory modes; golden repo Epic 3 (chat route on the same model)
