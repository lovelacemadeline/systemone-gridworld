"""Story 3.4 — HTTP backend for /v1/systemone servers (no network: mocked transports)."""

from __future__ import annotations

import json
import os

import httpx
import pytest

from gridworld.backends import build_request, call, make_backend
from gridworld.backends.fake import FakeBackend
from gridworld.backends.http import HTTPBackend, HTTPBackendError
from gridworld.sim import Action, generate_map

OBS = generate_map(3)


def mock_server(seen: list, status: int = 200):
    """An httpx MockTransport answering like a /v1/systemone server (via the fake)."""
    fake = FakeBackend()

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if status != 200:
            return httpx.Response(status, json={"detail": "bad", "errors": [{"loc": "state"}]})
        return httpx.Response(200, json=fake.decide(json.loads(request.content)))

    return httpx.MockTransport(handler)


def backend(seen, status=200, **kw):
    client = httpx.Client(base_url="http://test", transport=mock_server(seen, status))
    return HTTPBackend("http://test", client=client, **kw)


def test_one_tick_validates_and_carries_the_prefix():
    seen = []
    d = call(backend(seen), build_request(OBS, prefix="Rules v1.").request)
    assert d.action in Action
    (req,) = seen
    assert req.method == "POST" and req.url.path == "/v1/systemone"
    assert json.loads(req.content)["prefix"] == "Rules v1."


def test_bearer_token_from_env(monkeypatch):
    seen = []
    monkeypatch.setenv("MY_KEY", "s3cret")
    call(backend(seen, token_env="MY_KEY"), build_request(OBS).request)
    assert seen[0].headers["authorization"] == "Bearer s3cret"


def test_no_token_no_header(monkeypatch):
    seen = []
    monkeypatch.delenv("SYSTEMONE_API_KEY", raising=False)
    call(backend(seen), build_request(OBS).request)
    assert "authorization" not in seen[0].headers


def test_error_status_raises_with_body():
    with pytest.raises(HTTPBackendError, match="422") as exc:
        call(backend([], status=422), build_request(OBS).request)
    assert exc.value.status == 422 and "errors" in exc.value.body


def test_default_client_has_no_retries():
    b = make_backend("http", base_url="http://127.0.0.1:1", timeout=0.5)
    assert b.client._transport._pool._retries == 0
    assert b.id == "http:http://127.0.0.1:1"
    with pytest.raises(httpx.ConnectError):
        b.decide(build_request(OBS).request)


def test_against_the_golden_server_app_in_process():
    """The real mlx-classifiers Litestar app over its FakeRunner, via Litestar's TestClient."""
    pytest.importorskip("litestar")
    pytest.importorskip("mlx_classifiers")
    from litestar.testing import TestClient
    from mlx_classifiers.runner import FakeRunner
    from mlx_classifiers.server import create_app

    with TestClient(create_app(FakeRunner())) as client:
        b = HTTPBackend("http://testserver", client=client)
        for _ in range(2):
            d = call(b, build_request(OBS, prefix="Stable rules. " * 10).request)
        assert d.usage["output_tokens"] == 0
        assert b.last_headers["x-prefix-cache"] == "hit"  # the prefix arrived and was reused


@pytest.mark.server
@pytest.mark.skipif("GRIDWORLD_SERVER_URL" not in os.environ, reason="set GRIDWORLD_SERVER_URL")
def test_live_server_one_tick():
    """Against a running server, e.g. `mlx-classifiers serve` on http://127.0.0.1:8080."""
    b = HTTPBackend(os.environ["GRIDWORLD_SERVER_URL"])
    d = call(b, build_request(OBS).request)
    assert d.usage["output_tokens"] == 0
