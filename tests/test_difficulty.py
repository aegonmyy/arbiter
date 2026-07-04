"""Per-prompt difficulty routing and the confidence cascade."""
import arbiter.policy as policy_mod
from arbiter.classify import TaskType
from arbiter.difficulty import assess, route_key
from arbiter.policy import ALL_MODELS
from conftest import AUTH, FakeBTL, chat_body, make_completion

VALID_CODE = "```python\ndef add(a, b):\n    return a + b\n```"


def test_easy_prompts_use_the_base_bucket():
    assert assess(TaskType.MATH, "what is 2+2") == "easy"
    assert route_key(TaskType.MATH, "what is 2+2") == "math"
    assert assess(TaskType.CODE, "write a function to add two numbers") == "easy"


def test_hard_prompts_get_a_sub_bucket():
    hard = "Write an efficient O(n) algorithm and explain the tradeoffs step by step, handling edge cases"
    assert assess(TaskType.CODE, hard) == "hard"
    assert route_key(TaskType.CODE, hard) == "code:hard"
    long_math = "Prove the following theorem and derive the probability " + "x " * 200
    assert assess(TaskType.MATH, long_math) == "hard"


def test_hard_request_learns_in_its_own_bucket(make_client):
    fake = FakeBTL()
    client, app = make_client(fake)
    # "implement" makes the rules classify this as code without a model call.
    hard = "Implement an efficient function and explain the tradeoffs step by step, handling edge cases"
    r = client.post("/v1/chat/completions", json=chat_body(hard), headers=AUTH)
    assert r.status_code == 200, r.text
    assert r.json()["arbiter"]["difficulty"] == "hard"
    assert "code:hard" in app.state.policy.snapshot()


def test_confidence_cascade_escalates_a_weak_cheap_answer(make_client, monkeypatch):
    monkeypatch.setattr(policy_mod.random, "random", lambda: 0.99)  # no epsilon re-explore
    fake = FakeBTL()
    client, app = make_client(fake)
    pol = app.state.policy

    # Seed "code" so exploitation settles on the free model deepseek-v4-flash
    # (cost 0). Many samples so measured quality outweighs the benchmark prior.
    for m in ALL_MODELS:
        cost = 0.0 if m == "deepseek-v4-flash" else 0.01
        for _ in range(20):
            pol.record("code", m, 1.0, cost, 10)

    # The cheap model returns junk (fails the code check); stronger models return
    # valid code. The cascade should escalate and return the good answer.
    def responder(payload):
        if payload["model"] == "deepseek-v4-flash":
            return make_completion(text="sorry, I cannot help", model=payload["model"])
        return make_completion(text=VALID_CODE, model=payload["model"])
    fake.responder = responder

    r = client.post("/v1/chat/completions",
                    json=chat_body("write a function to add two numbers"), headers=AUTH)
    assert r.status_code == 200, r.text
    arb = r.json()["arbiter"]
    assert arb["cascaded_from"] == "deepseek-v4-flash"
    assert arb["model"] != "deepseek-v4-flash"
    assert arb["mode"] == "escalate"
    assert arb["quality"] >= 0.5           # the escalated answer passes the check
    assert fake.calls[0] == "deepseek-v4-flash"  # cheap tried first, then escalated
