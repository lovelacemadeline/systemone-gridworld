---
type: story
status: completed
title: Fake backend — oracle with controllable noise
owner: maddie
updated: 2026-10-16
anchor:
  - symbol: "src/gridworld/backends/fake.py::FakeBackend"
  - symbol: "src/gridworld/render/text.py::parse_text"
  - test: "tests/test_fake_backend.py::test_noise_zero_agrees_with_the_oracle_on_every_tick"
  - test: "tests/test_fake_backend.py::test_noise_lowers_agreement"
  - test: "tests/test_fake_backend.py::test_probabilities_are_plausible"
  - test: "tests/test_fake_backend.py::test_latency_is_reported_exactly_and_slept"
  - test: "tests/test_fake_backend.py::test_parse_text_inverts_to_text"
---

# Story 3.2 — Fake backend — oracle with controllable noise

Returns the oracle action with probability p and a random other action otherwise, with plausible probability vectors, and a fixed per-call latency to make timing tests deterministic.

## As built

- `FakeBackend(noise=0.0, latency_s=0.0, seed=0)` in `backends/fake.py`,
  registered as `make_backend("fake", ...)`. Like any backend it sees only
  the wire request (ADR-0002): it parses the state text back into an
  observation with `render/text.py::parse_text` (in image mode, the text
  block) and asks the oracle. With probability `noise` it answers a uniformly
  random other action.
- `parse_text` is product code, the inverse of `to_text`, because a backend
  needs it; it ignores anything after the status line (a memory tail) and
  returns seed 0 (the seed is not rendered). The independent test decoders of
  story 2.3 stay in `tests/`.
- Probabilities: the chosen action gets a seeded draw in [0.6, 0.95], the other
  five share the remainder equally, and `confidence` equals the top. `usage`
  estimates `input_tokens` as `len(prefix + text) // 4`, `output_tokens` 0.
  It sleeps `latency_s` and reports exactly that as `timing_ms.total`, so
  timing assertions are deterministic. One `random.Random(seed)` per backend:
  same seed and requests, same responses.

## Acceptance Criteria
- **Given** noise 0 **when** an episode runs **then** agreement is 100%.
- **Given** noise 0, 0.3 and 1 **when** episodes run **then** agreement is 100%, strictly between, and 0%.
