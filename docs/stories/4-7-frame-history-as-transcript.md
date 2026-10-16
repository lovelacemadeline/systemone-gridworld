---
type: story
status: completed
title: Frame history as a transcript — past frames stay cached
owner: maddie
updated: 2026-10-16
anchor:
  - symbol: "src/gridworld/harness/memory.py::FrameTranscriptMemory"
  - symbol: "src/gridworld/harness/memory.py::make_memory"
  - symbol: "src/gridworld/backends/request.py::build_request"
  - symbol: "src/gridworld/harness/report.py::run_name"
  - symbol: "src/gridworld/cli.py::build_parser"
  - test: "tests/test_frame_transcript.py::test_make_memory_picks_the_frame_transcript_in_image_mode"
  - test: "tests/test_frame_transcript.py::test_state_is_frames_and_answers_then_the_current_frame_and_text"
  - test: "tests/test_frame_transcript.py::test_past_frames_drop_to_half_when_full_and_the_window_slides"
  - test: "tests/test_frame_transcript.py::test_only_the_newest_frame_is_new_on_steady_state_ticks"
  - test: "tests/test_frame_transcript.py::test_the_naive_window_misses_every_tick_once_full"
  - test: "tests/test_frame_transcript.py::test_frames_flags_reach_the_run_name_and_meta"
---

# Story 4.7 — Frame history as a transcript

Maddie's hypothesis: seeing the last few frames may break the back-and-forth
ruts, because a strip of near-identical frames is a visual "nothing is
changing" signal. Done as a sliding window of k frames, every tick shifts the
sequence and the delta cache misses, so k frames cost k frame prefills per
tick. Done as a transcript (frame, answer, frame, answer, ...) the earlier
frames are a stable prefix: only the newest frame is prefilled, so history
costs about the same as no history. `--memory transcript` with `--mode image`
builds that sequence. `--frames k` caps how many past frames stay in the
transcript. `--frame-window` (sliding, naive) exists only for comparison.

## As built

- `make_memory("transcript", mode="image")` returns `FrameTranscriptMemory`,
  and the state is `[IMAGE_KEY, frame_{t-n}, "answer: <action>", ...,
  frame_{t-1}, "answer: <action>", frame_t, <text view>]`. With
  `--image-only` the text view is left out. The text-mode transcript is
  unchanged.
- **Cap.** If keeping one more frame would exceed `--frames k`, the transcript
  drops back to its newest `k // 2` frames, not one off the front. That tick
  is a cache miss, and the prefix is stable again after it. With k = 3 the
  ticks see 0, 1, 2, 3, 1, 2, 3, ... past frames, two in the mean.
  `--frames 0` sends no history, in the same layout. `--frame-window` always
  keeps the newest k frames, so once full the sequence shifts every tick.
- Run names gain `-f<k>` / `-fwin<k>`, and the meta gains `frames` and
  `frame_window` (only for an image transcript).
- **The cache, measured.** On the 26B (seed 4, `--frames 3`), steady ticks
  prefill 565 to 596 tokens: the answer, the frame (a 272-token run), the
  text view and the question. Cached tokens step 334, 609, 893, 1177 (+284,
  one frame and its answer, per tick). A drop tick prefills 840 to 885 tokens.
  The sliding window prefills 1408 to 1453 tokens every tick once full, with
  334 cached (the key and the rules only). Every tick encodes one image, about
  0.7 to 0.85 s. The fake-runner tests assert the same shape.

## Runs, 2026-10-16 (26B, seeds 0 to 4)

`gridworld play --backend local --model mlx-community/gemma-4-26B-A4B-it-qat-4bit --int8
--labels words --legal-only --mode image --memory transcript --episodes 5 --seed 0
--out runs/story-4-7` plus `--frames 3`, `--frames 0`, `--frames 3 --frame-window`.
Headless, low power mode **off** before and after, AC power, golden 316f7c5.
The rows are also in the story 5.4 table.

| run | completion | agreement | distinct/steps | reversals/ep | decisions/s | p50 ms | prefilled tok/tick | cached tok/tick |
|---|---|---|---|---|---|---|---|---|
| no history (`--frames 0`) | 80% | 56.6% | 0.57 | 48.8 | 0.67 | 1389 | 573 | 334 |
| transcript, `--frames 3` | 80% | 58.8% | 0.77 | 36.8 | 0.56 | 1605 | 666 | 791 |
| sliding window, `--frame-window 3` | 80% | 58.7% | 0.74 | 36.8 | 0.37 | 2431 | 1358 | 366 |

Per seed (outcome, steps, reversals): no history won 61/47, 15/1, 13/0,
20/5 and timed out on seed 4 (191). `--frames 3` won 15/0, 15/1, 13/0,
14/0 and timed out on seed 4 (183). The window run played nearly the same
episodes as `--frames 3`. Run dirs: `runs/story-4-7/20261016T202519Z-…-f0`,
`…20261016T201733Z-…-f3`, `…20261016T203315Z-…-fwin3`.

What it says: frame history removed the shorter ruts. Seed 0 went from 61
steps to 15, and reversals per episode fell from 48.8 to 36.8. It did not
break the seed 4 rut, which the 26B loses in every text and transcript
configuration. Only story 3.5's text + image with summary memory won it. The
transcript costs 16% more wall time per decision than no history; the
sliding window costs 75% more and plays no better.

## Acceptance Criteria
- **Given** `--mode image --memory transcript --frames 3` **when** tick t
  runs **then** `cached_tokens` covers all but the newest frame and the
  recorded encoder time is for one image. *(test_only_the_newest_frame_is_new_on_steady_state_ticks; 26B per-tick numbers above)*
- **Given** the naive window **when** the same run repeats **then** the
  report shows the per-tick cost difference. *(test_the_naive_window_misses_every_tick_once_full; the table above)*
- **Given** seeds 0 to 4 on the 26B **when** run with and without frame
  history **then** reversals per episode and completion are reported side by
  side. *(the table above and the 5.4 table; the outline's seeds 0 to 9 were narrowed to the five-episode protocol of the other 5.4 rows)*
