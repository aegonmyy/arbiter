"""The demo seed must be deterministic: math exploits the arbitrage model, and a
price spike on it re-routes to the fallback. If this breaks, the live demo breaks."""
import arbiter.policy as policy_mod
from arbiter import demo
from conftest import AUTH, FakeBTL


def test_seed_routes_math_to_arbitrage_model(make_client, monkeypatch):
    monkeypatch.setattr(policy_mod.random, "random", lambda: 0.99)  # no epsilon
    client, app = make_client(FakeBTL())

    r = client.post("/v1/demo/seed", headers=AUTH)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["routes_to"] == demo.ARBITRAGE_MODEL
    assert body["task_types"] == 5
    assert body["saved_pct"] > 0          # real savings vs the sampled baseline
    assert app.state.policy.choose("math").mode == "exploit"


def test_price_spike_reroutes_to_fallback(make_client, monkeypatch):
    monkeypatch.setattr(policy_mod.random, "random", lambda: 0.99)
    client, app = make_client(FakeBTL())
    client.post("/v1/demo/seed", headers=AUTH)
    pol = app.state.policy
    assert pol.choose("math").model == demo.ARBITRAGE_MODEL

    # Simulate the bumped call the runtime would bill after a price spike: a much
    # higher cost for the same tokens triggers the drift detector.
    shift = pol.record("math", demo.ARBITRAGE_MODEL, 0.93, 4e-5, tokens=100)
    assert shift is not None and shift["direction"] == "up"

    # It now routes to the next-cheapest good model.
    assert pol.choose("math").model == demo.FALLBACK_MODEL


def test_seed_prewarms_cache(make_client):
    client, app = make_client(FakeBTL())
    client.post("/v1/demo/seed", headers=AUTH)
    assert len(app.state.cache) == 1
    hit = app.state.cache.lookup(demo.CACHE_PROMPT)   # lexical (no embedder in tests)
    assert hit is not None
