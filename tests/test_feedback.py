"""Human thumbs up/down feedback: the strongest quality signal, overrides the judge."""
from arbiter.policy import Policy
from conftest import AUTH, FakeBTL, chat_body


def test_feedback_moves_blended_quality(tmp_path):
    p = Policy(db_path=str(tmp_path / "p.db"))
    task, model = "open", "deepseek-v4-flash"
    base = p._blended_quality(task, model)  # prior only

    # Downvotes pull the estimate down.
    for _ in range(3):
        p.add_feedback(task, model, up=False)
    after_down = p._blended_quality(task, model)
    assert after_down < base

    # Upvotes pull it back up, above where the downvotes left it.
    for _ in range(10):
        p.add_feedback(task, model, up=True)
    after_up = p._blended_quality(task, model)
    assert after_up > after_down
    assert after_up > 0.5


def test_feedback_overrides_a_positive_judge(tmp_path):
    # The judge measured high quality, but humans keep downvoting: routing quality
    # should end up low.
    p = Policy(db_path=str(tmp_path / "p.db"))
    task, model = "open", "hermes-3-llama-3.1-405b"
    for _ in range(3):
        p.record(task, model, quality=1.0, cost=0.0, tokens=10)
    assert p._blended_quality(task, model) > 0.8
    for _ in range(8):
        p.add_feedback(task, model, up=False)
    assert p._blended_quality(task, model) < 0.5


def test_feedback_endpoint_records_and_validates(make_client):
    fake = FakeBTL()
    client, app = make_client(fake)

    ok = client.post("/v1/feedback",
                     json={"model": "deepseek-v4-flash", "task": "code", "rating": "up"},
                     headers=AUTH)
    assert ok.status_code == 200, ok.text
    assert ok.json()["up"] == 1
    assert app.state.policy.feedback_counts("code", "deepseek-v4-flash") == (1, 0)

    # Unknown model and bad rating are rejected.
    assert client.post("/v1/feedback",
                       json={"model": "nope", "task": "code", "rating": "up"},
                       headers=AUTH).status_code == 422
    assert client.post("/v1/feedback",
                       json={"model": "deepseek-v4-flash", "task": "code", "rating": "meh"},
                       headers=AUTH).status_code == 422


def test_feedback_shows_in_snapshot(make_client):
    fake = FakeBTL()
    client, app = make_client(fake)
    app.state.policy.record("code", "deepseek-v4-flash", 1.0, 0.0, 10)
    app.state.policy.add_feedback("code", "deepseek-v4-flash", up=True)
    entry = client.get("/v1/policy").json()["code"][0]
    assert entry["up"] == 1 and entry["down"] == 0
