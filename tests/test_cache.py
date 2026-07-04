"""Near-duplicate response cache: a near-identical prompt is served for free."""
from arbiter.cache import SemanticCache
from conftest import AUTH, FakeBTL, chat_body


def test_exact_and_near_duplicate_hit():
    c = SemanticCache(threshold=0.85, min_tokens=4)
    c.store("What is the capital of France", {"answer": "Paris"})
    # Exact (case/space) and lightly reworded both hit.
    assert c.lookup("what is the capital of france")["data"]["answer"] == "Paris"
    assert c.lookup("What  is the CAPITAL of France???")["data"]["answer"] == "Paris"
    # The similarity is reported.
    assert c.lookup("what is the capital of france")["similarity"] >= 0.85


def test_unrelated_prompt_misses():
    c = SemanticCache(threshold=0.85, min_tokens=4)
    c.store("What is the capital of France", {"answer": "Paris"})
    assert c.lookup("Write a poem about the ocean tides") is None


def test_short_prompts_are_not_cached():
    c = SemanticCache(min_tokens=4)
    c.store("hi there", {"answer": "x"})
    assert len(c) == 0
    assert c.lookup("hi there") is None


def test_fifo_eviction():
    c = SemanticCache(max_entries=2, min_tokens=2)
    c.store("alpha beta gamma", {"answer": 1})
    c.store("delta epsilon zeta", {"answer": 2})
    c.store("eta theta iota", {"answer": 3})
    assert len(c) == 2
    assert c.lookup("alpha beta gamma") is None  # evicted


def test_near_duplicate_request_served_from_cache(make_client):
    fake = FakeBTL()
    client, app = make_client(fake)

    first = client.post("/v1/chat/completions",
                        json=chat_body("What is the capital of France"), headers=AUTH)
    assert first.status_code == 200
    assert first.json()["arbiter"]["cache"] == "miss"
    calls_after_first = len(fake.calls)
    assert calls_after_first >= 1

    second = client.post("/v1/chat/completions",
                         json=chat_body("what is the capital of france?"), headers=AUTH)
    assert second.status_code == 200
    arb = second.json()["arbiter"]
    assert arb["cache"] == "hit"
    assert arb["cost"] == 0.0
    assert arb["cache_similarity"] >= 0.85
    # No new upstream calls were made for the cached answer.
    assert len(fake.calls) == calls_after_first


def test_no_cache_flag_disables_caching(make_client):
    fake = FakeBTL()
    client, app = make_client(fake)
    body = chat_body("What is the tallest mountain in the world", arbiter_no_cache=True)
    client.post("/v1/chat/completions", json=body, headers=AUTH)
    # Nothing was stored, and the flag was stripped from the forwarded payload.
    assert len(app.state.cache) == 0
    assert all("arbiter_no_cache" not in pl for pl in fake.payloads)
