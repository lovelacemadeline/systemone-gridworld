---
type: story
status: completed
title: HTTP backend for /v1/systemone servers
owner: maddie
updated: 2026-10-16
anchor:
  - symbol: "src/gridworld/backends/http.py::HTTPBackend"
  - symbol: "src/gridworld/backends/http.py::HTTPBackendError"
  - test: "tests/test_http_backend.py::test_one_tick_validates_and_carries_the_prefix"
  - test: "tests/test_http_backend.py::test_bearer_token_from_env"
  - test: "tests/test_http_backend.py::test_error_status_raises_with_body"
  - test: "tests/test_http_backend.py::test_default_client_has_no_retries"
  - test: "tests/test_http_backend.py::test_against_the_golden_server_app_in_process"
  - test: "tests/test_http_backend.py::test_live_server_one_tick"
---

# Story 3.4 — HTTP backend for /v1/systemone servers

httpx client with base URL, optional bearer token from an env var, timeout, and retries off by default so latency is honest.

## As built

- `HTTPBackend(base_url="http://127.0.0.1:8080", token_env="SYSTEMONE_API_KEY",
  timeout=30.0, client=None)` in `backends/http.py`, registered as
  `make_backend("http", ...)`. It POSTs the request dict to `/v1/systemone`
  and returns the JSON reply for the adapter to validate.
- The bearer token comes from `token_env` only when that variable is set. The
  default transport has `retries=0`; timeouts and connection errors
  propagate. A non-2xx reply raises `HTTPBackendError` with status and body
  (the golden server's 422 lists field paths). `last_headers` keeps the last
  reply's headers, e.g. the golden server's `x-prefix-cache`.
- Tests need no network: an httpx `MockTransport` stub (answering via the fake
  backend) checks route, prefix, auth and errors; the golden server's real
  Litestar app over its `FakeRunner` runs in-process through Litestar's
  `TestClient`, and its second tick reports `x-prefix-cache: hit`, proving the
  prefix arrived and was reused. A `server`-marked test, skipped unless
  `GRIDWORLD_SERVER_URL` is set, targets a live server. Run on 2026-10-16
  against `mlx-classifiers serve` (E2B) on localhost: three ticks of 341 input
  tokens took about 108-150 ms wall each, prefix cache hit.

## Acceptance Criteria
- **Given** a local mlx-classifiers server **when** one tick runs **then** the response validates and the request carried the prefix.
- **Given** a server error status **when** called **then** `HTTPBackendError` carries the status and body, with no retry.
