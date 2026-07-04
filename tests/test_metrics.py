"""Durable metrics: the feed, alerts and classifier counters live in the policy
DB, so they survive a restart and back a time series."""
from arbiter.policy import Policy
from conftest import AUTH, FakeBTL, chat_body


def _event(ts, model="deepseek-v4-flash", cost=0.0):
    return {"ts": ts, "task": "open", "classified_by": "rules", "model": model,
            "mode": "exploit", "quality": 0.9, "cost": cost, "saved": 0.0,
            "failover_from": None}


def test_feed_and_counters_survive_a_restart(tmp_path):
    db = str(tmp_path / "p.db")
    p = Policy(db_path=db)
    p.add_event(_event(1000.0))
    p.add_event(_event(1001.0, model="gpt-4o"))
    p.bump_counter("rules")
    p.bump_counter("rules")
    p.bump_counter("model")

    # Re-open the same DB, as a fresh process would after a redeploy.
    p2 = Policy(db_path=db)
    events = p2.recent_events()
    assert [e["model"] for e in events] == ["gpt-4o", "deepseek-v4-flash"]  # newest first
    assert p2.counters()["rules"] == 2
    assert p2.counters()["model"] == 1
    assert p2.counters()["model-fallback"] == 0


def test_feed_is_bounded(tmp_path):
    p = Policy(db_path=str(tmp_path / "p.db"))
    for i in range(Policy.FEED_KEEP + 50):
        p.add_event(_event(1000.0 + i))
    kept = p._db.execute("SELECT COUNT(*) FROM feed").fetchone()[0]
    assert kept == Policy.FEED_KEEP


def test_alerts_persist_and_count(tmp_path):
    p = Policy(db_path=str(tmp_path / "p.db"))
    p.add_alert({"task": "math", "model": "deepseek-chat-v3",
                 "old_unit": 1e-6, "new_unit": 8e-6, "direction": "up"})
    assert p.alert_count() == 1
    a = p.recent_alerts()[0]
    assert a["direction"] == "up" and a["model"] == "deepseek-chat-v3"


def test_timeseries_buckets_calls(tmp_path):
    import time
    p = Policy(db_path=str(tmp_path / "p.db"))
    now = time.time()
    for i in range(5):
        p.add_event(_event(now - 10, cost=0.001))  # all in the most recent bucket
    series = p.timeseries(bucket_seconds=3600, buckets=24)
    assert len(series) == 24
    assert series[-1]["calls"] == 5
    assert abs(series[-1]["spend"] - 0.005) < 1e-9


def test_endpoints_serve_durable_metrics(make_client):
    fake = FakeBTL()
    client, app = make_client(fake)
    r = client.post("/v1/chat/completions", json=chat_body("calculate 2+2"), headers=AUTH)
    assert r.status_code == 200

    recent = client.get("/v1/recent").json()
    assert len(recent) == 1 and recent[0]["task"] == "math"
    overview = client.get("/v1/overview").json()
    assert overview["classifier"]["rules"] >= 1
    ts = client.get("/v1/timeseries").json()
    assert isinstance(ts, list) and ts[-1]["calls"] >= 1
