"""HTTP backend (story 3.4): any server speaking ``POST /v1/systemone``.

``mlx-classifiers serve``, a Jev-style hosted API, later the Swift port: one
httpx client per backend, ``base_url`` plus the route, the request dict as the
JSON body, the JSON reply returned as-is for the adapter to validate.

- **Auth**: if the environment variable ``token_env`` (default
  ``SYSTEMONE_API_KEY``) is set, it is sent as ``Authorization: Bearer ...``.
- **No retries** (transport ``retries=0``) so measured latency is honest; a
  timeout or connection error propagates as the httpx exception.
- **Errors**: a non-2xx reply raises :class:`HTTPBackendError` carrying the
  status and the server's body (the golden server's 422 lists field paths).
- ``last_headers`` keeps the most recent reply's headers for diagnostics, e.g.
  the golden server's ``x-prefix-cache: hit|miss|none``.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

__all__ = ["ROUTE", "HTTPBackend", "HTTPBackendError"]

ROUTE = "/v1/systemone"


class HTTPBackendError(RuntimeError):
    """The server answered with a non-2xx status."""

    def __init__(self, status: int, body: str):
        self.status, self.body = status, body
        super().__init__(f"POST {ROUTE} -> {status}: {body[:500]}")


class HTTPBackend:
    """``POST {base_url}/v1/systemone``. Pass ``client`` to inject a test transport."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8080",
        *,
        token_env: str = "SYSTEMONE_API_KEY",
        timeout: float = 30.0,
        client: httpx.Client | None = None,
        id: str | None = None,
    ) -> None:
        headers = {}
        token = os.environ.get(token_env) if token_env else None
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if client is None:
            client = httpx.Client(
                base_url=base_url,
                timeout=timeout,
                transport=httpx.HTTPTransport(retries=0),
            )
        client.headers.update(headers)
        self.client = client
        self.base_url = base_url
        self.id = id or f"http:{base_url}"
        self.last_headers: httpx.Headers | None = None

    def decide(self, request: dict[str, Any]) -> dict[str, Any]:
        reply = self.client.post(ROUTE, json=request)
        self.last_headers = reply.headers
        if not reply.is_success:
            raise HTTPBackendError(reply.status_code, reply.text)
        return reply.json()

    def close(self) -> None:
        self.client.close()
