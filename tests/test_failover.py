"""In-request failover: a routed model that errors is quarantined and the
next-best live model is tried, within the same request."""
from conftest import AUTH, FakeBTL, chat_body, http_error, make_completion


def _responder(fail: set[str]):
    def responder(payload):
        m = payload["model"]
        if m in fail:
            raise http_error(429, {"error": "rate_limited"})
        return make_completion(text="4", model=m)
    return responder


def test_failover_routes_around_a_broken_model(make_client):
    # The first-choice model (least sampled) errors; the request should still
    # succeed on a fallback model rather than returning the error.
    fake = FakeBTL(_responder(fail={"deepseek-v4-flash"}))
    client, app = make_client(fake)

    r = client.post("/v1/chat/completions", json=chat_body("calculate 2+2"), headers=AUTH)
    assert r.status_code == 200, r.text
    arb = r.json()["arbiter"]
    assert arb["model"] != "deepseek-v4-flash"
    assert arb["failover_from"] == ["deepseek-v4-flash"]
    # The broken model was tried first, then a fallback served.
    assert fake.calls[0] == "deepseek-v4-flash"
    assert len(fake.calls) == 2
    # And it is now quarantined so later requests skip it up front.
    assert "deepseek-v4-flash" in app.state.quarantine


def test_all_attempts_failing_surfaces_the_upstream_error(make_client):
    fake = FakeBTL(lambda payload: (_ for _ in ()).throw(http_error(503, {"error": "down"})))
    client, app = make_client(fake)

    r = client.post("/v1/chat/completions", json=chat_body("calculate 2+2"), headers=AUTH)
    assert r.status_code == 503, r.text
    detail = r.json()["detail"]
    assert detail["upstream"] == "btl_runtime"
    # It gave up after MAX_ATTEMPTS distinct models.
    assert len(detail["tried"]) == 3
    assert len(set(detail["tried"])) == 3


def test_no_failover_when_first_choice_succeeds(make_client):
    fake = FakeBTL(_responder(fail=set()))
    client, app = make_client(fake)

    r = client.post("/v1/chat/completions", json=chat_body("calculate 2+2"), headers=AUTH)
    assert r.status_code == 200, r.text
    assert r.json()["arbiter"]["failover_from"] is None
    assert len(fake.calls) == 1
