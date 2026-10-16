---
type: story
status: pending
title: Frame history as a transcript — past frames stay cached
owner: maddie
updated: 2026-10-16
anchor: none  # outlined only; depends on 3.5 and on delta caching in the golden library (landed as its 3.4)
---

# Story 4.7 — Frame history as a transcript

Maddie's hypothesis: seeing the last few frames may break the back-and-forth
ruts, because a strip of near-identical frames is a visual "nothing is
changing" signal. Done as a sliding window of k frames, every tick shifts the
sequence and the delta cache misses, so k frames cost k encodes and k frame
prefills per tick. Done as a transcript (frame, answer, frame, answer, ...)
the earlier frames are a stable prefix: only the newest frame is encoded and
prefilled, so history costs the same as no history. `--memory transcript`
with `--mode image` builds that sequence; `--frames k` caps how many past
frames stay in the transcript (older ones drop off the front, which is a
cache miss once, then stable again), and `--frame-window` (sliding, naive)
exists only as the comparison.

## Acceptance Criteria
- **Given** `--mode image --memory transcript --frames 3` **when** tick t
  runs **then** `cached_tokens` covers all but the newest frame and the
  recorded encoder time is for one image.
- **Given** the naive window **when** the same run repeats **then** the
  report shows the per-tick cost difference.
- **Given** seeds 0 to 9 on the 26B **when** run with and without frame
  history **then** reversals per episode and completion are reported side by
  side.
