---
type: story
status: completed
title: In-process backend over mlx-classifiers decide()
owner: maddie
updated: 2026-10-16
anchor:
  - symbol: "src/gridworld/backends/local.py::LocalBackend"
  - symbol: "src/gridworld/backends/local.py::LocalBackend.decide"
  - test: "tests/test_local_backend.py::test_one_tick_validates_with_zero_output_tokens"
  - test: "tests/test_local_backend.py::test_prefix_cache_is_reused_across_ticks"
  - test: "tests/test_local_backend.py::test_real_model_one_tick"
---

# Story 3.3 — In-process backend over mlx-classifiers decide()

Optional extra: wraps `mlx_classifiers.decide` with an `MLXRunner`, passing the prefix through so caching works. Skipped in CI without the library.

## As built

- `LocalBackend(model="mlx-community/gemma-4-E2B-it-qat-4bit", int8=False,
  calibration=None, runner=None)` in `backends/local.py`, registered as
  `make_backend("local", ...)`. `mlx_classifiers` is imported when the backend
  is constructed; without it the `ImportError` names the `local` extra. The
  extra now pins `mlx==0.32.0` and `mlx-lm==0.31.3` (what the golden library
  was built on); this venv has the sibling checkout installed editable.
- The wire dict is validated into the library's `SystemOneRequest` and
  answered with `decide(...).to_wire()`, so the backend speaks only the schema.
- **Prefix caching across ticks**: `decide` caches the prefix once per call,
  so the runner is wrapped in a small LRU memo of `cache_prefix` keyed by
  token ids (the in-process twin of the server's `PrefixLRU`). Each tick after
  the first reuses the cached prefix, which `usage.cached_tokens` shows.
- **Calibration** defaults to the library's default calibration file, as
  `mlx-classifiers serve` does, so in-process and HTTP results are comparable.
- **Image mode** raised `NotImplementedError` while the golden library had no
  vision port; story 3.5 removed that once it did (golden Epic 6).
- Tests run the wiring against the golden `FakeRunner` (no weights), and one
  `mlx`-marked test runs the real E2B model when it is in the HF cache.
  Measured on 2026-10-16 (M-series, low power mode): load about 2 s; three ticks
  of 341 input tokens (53 cached prefix) took about 890 ms (first, warm-up),
  then 117 and 157 ms wall.

## Acceptance Criteria
- **Given** the golden library installed **when** one tick runs **then** the response validates and `output_tokens` is 0.
- **Given** several ticks sharing a prefix **when** run **then** the prefix is cached once and reused.
- **Given** an image-mode request **when** decided **then** `NotImplementedError` explains why. *(Retired by story 3.5: image requests are now decided.)*
