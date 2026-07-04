"""Shared test fixtures.

Tests never touch the network or the real seeded database. Each test gets a
fresh temp policy store, client auth satisfied by an operator key, and the BTL
client replaced with an in-process fake whose behaviour the test controls.
"""
import httpx
import pytest
from starlette.testclient import TestClient

from arbiter.btl import Completion, Cost


def make_completion(text: str = "ok", charge: float | None = 0.0,
                    total_tokens: int = 10, model: str = "m") -> Completion:
    body = {
        "choices": [{"message": {"role": "assistant", "content": text}}],
        "usage": {"total_tokens": total_tokens},
    }
    return Completion(body=body, cost=Cost(charged=charge), model=model)


def http_error(status: int, detail: dict | None = None) -> httpx.HTTPStatusError:
    req = httpx.Request("POST", "https://api.badtheorylabs.com/v1/chat/completions")
    resp = httpx.Response(status, json=detail or {"error": "upstream"}, request=req)
    return httpx.HTTPStatusError(f"{status}", request=req, response=resp)


class FakeBTL:
    """Stand-in for BTLClient. `responder(payload) -> Completion` may raise an
    httpx error to simulate an upstream failure. `models_data` backs models()."""

    def __init__(self, responder=None, models_data=None):
        self.responder = responder or (lambda payload: make_completion(model=payload["model"]))
        self.models_data = models_data or {"data": []}
        self.calls: list[str] = []

    async def chat(self, payload):
        self.calls.append(payload["model"])
        return self.responder(payload)

    async def models(self):
        return self.models_data

    def stream(self, payload):  # not exercised by the sync failover tests
        raise NotImplementedError

    async def aclose(self):
        pass


@pytest.fixture
def make_client(monkeypatch, tmp_path):
    """Factory: build a TestClient wired to a given FakeBTL. Returns (client, app)."""
    monkeypatch.setenv("ARBITER_DB", str(tmp_path / "test.db"))
    monkeypatch.setenv("GATEWAY_API_KEY", "test-btl-key")
    from arbiter import config
    monkeypatch.setattr(config, "ARBITER_API_KEYS", frozenset({"op-key"}))

    def _build(fake: FakeBTL | None = None):
        from arbiter.main import app
        client = TestClient(app)
        client.__enter__()  # run lifespan startup
        app.state.btl = fake or FakeBTL()
        return client, app

    built: list[TestClient] = []

    def factory(fake=None):
        client, app = _build(fake)
        built.append(client)
        return client, app

    yield factory
    for c in built:
        c.__exit__(None, None, None)


AUTH = {"Authorization": "Bearer op-key"}


def chat_body(text="hello there, tell me a story", **extra):
    body = {"model": "ignored", "messages": [{"role": "user", "content": text}]}
    body.update(extra)
    return body
