---
type: story
status: completed
title: Image mode through the local backend
owner: maddie
updated: 2026-10-16
anchor:
  - symbol: "src/gridworld/backends/local.py::LocalBackend.decide"
  - symbol: "src/gridworld/backends/request.py::build_request"
  - symbol: "src/gridworld/backends/request.py::IMAGE_KEY"
  - symbol: "src/gridworld/backends/request.py::BuiltRequest"
  - symbol: "src/gridworld/backends/schema.py::validate_request"
  - symbol: "src/gridworld/record.py::TickRecord"
  - symbol: "src/gridworld/harness/score.py::RunSummary"
  - test: "tests/test_local_backend.py::test_image_tick_validates_and_reports_the_encoder"
  - test: "tests/test_local_backend.py::test_the_image_changes_the_answer_on_the_fake_runner"
  - test: "tests/test_local_backend.py::test_image_episode_records_frame_sha256_and_encoder_ms"
  - test: "tests/test_local_backend.py::test_image_request_carries_one_image_block"
  - test: "tests/test_local_backend.py::test_image_only_session_names_the_run_and_records_meta"
  - test: "tests/test_local_backend.py::test_real_model_one_image_tick"
  - test: "tests/test_backend_schema.py::test_image_request_carries_text_and_png_block"
  - test: "tests/test_backend_schema.py::test_image_only_drops_the_text_view_but_keeps_the_memory_tail"
  - test: "tests/test_backend_schema.py::test_malformed_image_blocks_fail_the_vendored_schema"
---

# Story 3.5 — Image mode through the local backend

`LocalBackend` raised for image blocks (story 3.3). The golden library now
accepts `{"type": "image/png", "base64": ...}` blocks in a list state (its
Epic 6, field for field the block this repo proposed), so the schema is
re-vendored, the local extension is gone, and `--mode image` flows through
`decide` unchanged. Encoder time is recorded per tick, and the text view stays
beside the image by default (`--image-only` drops it) so the variants compare
on identical states.

## As built

- **Schema.** `schema/*.json` re-vendored from golden 316f7c5 (schema last
  changed in 0e0fe18; `options.delta_cache` arrived in f1591f5).
  `schema/local-extensions.md` and `extended_request_schema` /
  `uses_local_extensions` are deleted: every request and response is checked
  against the vendored files as they are.
- **Request.** Image mode sends `[IMAGE_KEY, <frame block>, <text view>]`.
  `IMAGE_KEY` is one stable sentence on what the colours mean (the golden
  battery's own key), so it sits in the cached prefix. `--image-only` sends
  `[IMAGE_KEY, <frame block>]`, plus the memory tail as its own text block
  when there is one, so `--memory summary` stays the same between the two
  image variants. `BuiltRequest.frame_sha256` is the sha256 of the PNG sent.
  The fake backend still reads the last text block, so it needs the text view
  (it cannot play `--image-only`).
- **Backend.** `LocalBackend.decide` no longer refuses images. The vendored
  `timing_ms` is open, so the backend adds `timing_ms.encoder`: the vision
  tower ms the runner logged for this decision (`MLXRunner.vision_encode_ms`).
  It is 0 when the frame was memoised, and absent on text requests. The prefix
  memo passes image-carrying `cache_prefix` calls straight to the runner.
- **Records.** Each tick records `frame_sha256` and, when reported,
  `timing.encoder_ms`. The run summary gains `p50_encoder_ms` and the meta
  `image_only`; image-only run names read `-image-only-`.
- One `mlx` test plays two E2B image ticks: 685 input + 259 cached tokens on
  the first tick, encoder 328 ms (first) and 194 ms, wall 542 / 307 ms; low
  power mode off, AC.

## Runs, 2026-10-16 (26B, three modes)

`gridworld play --backend local --model mlx-community/gemma-4-26B-A4B-it-qat-4bit --int8
--labels words --legal-only --memory summary --episodes 5 --seed 0 --out runs/story-3-5`
with `--mode text`, `--mode image`, `--mode image --image-only`, headless,
low power mode **off** before and after, AC power, golden 316f7c5. The rows
are in the story 5.4 table. Per seed (outcome, steps, reversals):

| mode | seed 0 | seed 1 | seed 2 | seed 3 | seed 4 | p50 encoder ms |
|---|---|---|---|---|---|---|
| text | won 13, 0 | won 13, 0 | won 15, 1 | won 14, 0 | timeout 200, 186 | - |
| text + image | won 15, 1 | won 13, 0 | won 13, 0 | won 14, 0 | **won 99, 62** | 709 |
| image only | timeout 200, 151 | won 13, 0 | died 12, 2 | won 22, 8 | timeout 200, 197 | 836 |

Run dirs: `runs/story-3-5/20261016T195935Z-…-int8-text-summary-legal-words`,
`…20261016T200046Z-…-int8-image-summary-legal-words`,
`…20261016T200419Z-…-int8-image-only-summary-legal-words`.

The frame helps when the text is there too: text + image is the first
configuration to win seed 4, the one the text 26B always loses in a
back-and-forth rut. It still ruts for a while there (62 reversals), but gets
out. From pixels alone the 26B wins 2 of 5. It costs about 5.5x the text
run's wall time per decision (1.29 s against 0.24 s p50). The encoder is
about 0.7 to 0.8 s of that, as the golden 6.3 bench measured.

## Acceptance Criteria
- **Given** `--backend local --mode image` **when** one tick runs **then** the
  response validates against the re-vendored schema and the request carried
  one image block with the frame's sha256 recorded in the tick. *(test_image_tick_validates_and_reports_the_encoder, test_image_episode_records_frame_sha256_and_encoder_ms, test_real_model_one_image_tick)*
- **Given** the same seed **when** run in text, image, and text-plus-image
  modes **then** the report lists the three side by side. *(the story 5.4 table and `gridworld compare` over the three run reports)*
