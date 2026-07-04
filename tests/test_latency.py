"""Latency-aware routing: latency is measured per model and an optional
arbiter_max_latency ceiling filters slow models out for interactive paths."""
import arbiter.policy as policy_mod
from arbiter.policy import ALL_MODELS, Policy
from conftest import AUTH, FakeBTL, chat_body


def test_latency_is_recorded_and_averaged(tmp_path):
    p = Policy(db_path=str(tmp_path / "p.db"))
    p.record("open", "gpt-4o", quality=0.9, cost=0.0, tokens=10, latency=0.2)
    p.record("open", "gpt-4o", quality=0.9, cost=0.0, tokens=10, latency=0.4)
    assert abs(p.latency_of("open", "gpt-4o") - 0.3) < 1e-9
    snap = p.snapshot()["open"][0]
    assert snap["avg_latency_ms"] == 300


def test_untimed_model_has_no_latency(tmp_path):
    p = Policy(db_path=str(tmp_path / "p.db"))
    assert p.latency_of("open", "gpt-4o") is None


def test_latency_cap_excludes_slow_models(make_client, monkeypatch):
    monkeypatch.setattr(policy_mod.random, "random", lambda: 0.99)  # no epsilon
    fake = FakeBTL()
    client, app = make_client(fake)
    pol = app.state.policy
    task = "code"
    # Time every model: one is fast, the rest are slow. Two samples each so no
    # model is left to explore and routing goes straight to exploit.
    for m in ALL_MODELS:
        lat = 0.05 if m == "deepseek-v4-flash" else 2.0
        pol.record(task, m, 1.0, 0.0, 10, lat)
        pol.record(task, m, 1.0, 0.0, 10, lat)

    body = chat_body("write a function to add two numbers", arbiter_max_latency=0.5)
    r = client.post("/v1/chat/completions", json=body, headers=AUTH)
    assert r.status_code == 200, r.text
    arb = r.json()["arbiter"]
    assert arb["model"] == "deepseek-v4-flash"      # only model under the cap
    assert arb["latency_capped"] is True
    assert arb["max_latency"] == 0.5
    assert isinstance(arb["latency_ms"], int) and arb["latency_ms"] >= 0
    # The non-standard field must not be forwarded to the runtime.
    assert all("arbiter_max_latency" not in pl for pl in fake.payloads)
