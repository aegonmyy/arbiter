"""Semantic (embedding-based) cache matching, with a fake embedder so no network
call is made. Proves it catches paraphrases the lexical matcher misses."""
from arbiter.cache import SemanticCache
from arbiter.embeddings import cosine
from conftest import AUTH, FakeBTL, FakeEmbedder, chat_body


def test_cosine():
    assert abs(cosine([1, 0], [1, 0]) - 1.0) < 1e-9
    assert abs(cosine([1, 0], [0, 1])) < 1e-9
    assert cosine([], [1]) == 0.0
    assert cosine([1, 2, 3], [2, 4, 6]) > 0.999  # same direction


def test_cache_matches_by_vector_when_provided():
    c = SemanticCache(semantic_threshold=0.83, min_tokens=2)
    c.store("what is the capital of france", {"a": 1}, vector=[1.0, 0.0])
    # Different words, but a near-identical vector -> hit (lexical would miss).
    hit = c.lookup("name the capital city of france", vector=[0.98, 0.02])
    assert hit is not None and hit["mode"] == "semantic" and hit["data"]["a"] == 1
    # A distant vector misses even with some shared words.
    assert c.lookup("capital gains tax rules", vector=[0.0, 1.0]) is None


# France-ish prompts embed to one direction, everything else to another.
def _france_mapping(text):
    t = text.lower()
    return [1.0, 0.0] if ("france" in t or "capital" in t) else [0.0, 1.0]


def test_paraphrase_hits_semantically_via_endpoint(make_client):
    fake = FakeBTL()
    client, app = make_client(fake, embedder=FakeEmbedder(_france_mapping))

    first = client.post("/v1/chat/completions",
                        json=chat_body("What is the capital of France"), headers=AUTH)
    assert first.status_code == 200
    assert first.json()["arbiter"]["cache"] == "miss"
    calls_after_first = len(fake.calls)

    # Reworded with mostly different words - lexical Jaccard would miss this, but
    # the embedding vectors match.
    second = client.post("/v1/chat/completions",
                         json=chat_body("Name the capital city of France"), headers=AUTH)
    arb = second.json()["arbiter"]
    assert arb["cache"] == "hit"
    assert arb["cache_mode"] == "semantic"
    assert arb["cost"] == 0.0
    assert len(fake.calls) == calls_after_first  # no new upstream call


def test_objective_tasks_do_not_semantically_over_match(make_client):
    # Even if the embedder maps two different math prompts to the same vector,
    # they must not cache-collide (different numbers = different answers). Math
    # falls back to lexical, so the differently-worded prompt is a miss.
    everything_same = FakeEmbedder(lambda text: [1.0, 0.0])
    fake = FakeBTL()
    client, app = make_client(fake, embedder=everything_same)

    first = client.post("/v1/chat/completions",
                        json=chat_body("Calculate 37 times 24"), headers=AUTH)
    assert first.json()["arbiter"]["cache"] == "miss"
    second = client.post("/v1/chat/completions",
                         json=chat_body("Calculate 89 times 11"), headers=AUTH)
    assert second.json()["arbiter"]["cache"] == "miss"   # not a false semantic hit


def test_factual_paraphrase_still_hits_with_the_gate(make_client):
    # Factual questions keep semantic matching (meaning determines the answer).
    fake = FakeBTL()
    client, app = make_client(fake, embedder=FakeEmbedder(_france_mapping))
    client.post("/v1/chat/completions",
                json=chat_body("What is the capital of France"), headers=AUTH)
    r = client.post("/v1/chat/completions",
                    json=chat_body("Name the capital city of France"), headers=AUTH)
    assert r.json()["arbiter"]["cache"] == "hit"


def test_overview_reports_cache_mode(make_client):
    fake = FakeBTL()
    # Lexical when no embedder.
    client, app = make_client(fake, embedder=None)
    assert client.get("/v1/overview").json()["cache_mode"] == "lexical"
