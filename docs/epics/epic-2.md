---
type: epic
status: in-progress
title: Renderers — text, image, live view
epic: 2
owner: maddie
updated: 2026-10-16
---

# Epic 2 — Renderers — text, image, live view

Pure functions of the observation: `to_text` (stable parts first, volatile line last, for prefix caching), `to_image` (small PNG, one tile code shared with the window), and the pygame live view that shows the map, the backend probability bars, the oracle pick, and decisions/s. Text and image are lossless with respect to the grid and are tested as such (ADR-0001).

## Stories
| id | title | status |
|---|---|---|
| 2.1 | Text renderer with stable-first layout | completed |
| 2.2 | Image renderer and the shared tile code | completed |
| 2.3 | Lossless round-trip test between text, image and observation | pending |
| 2.4 | Live view window with probability bars and oracle overlay | pending |
## Related
- ADR-0001
