"""Demo staging: put the instance into a known, repeatable state.

A live demo should not depend on exploration luck. `seed` writes a curated policy
directly (deterministic, costs nothing), so the dashboard looks learned and the
price-arbitrage moment lands every time:

- The `math` task is fully seeded across the whole pool so it is in exploit mode
  and routes to `deepseek-chat-v3` (the cheapest model still within quality
  tolerance). `gpt-4o-mini` is the next-cheapest good one, so a price spike on the
  chosen model re-routes there and fires an alert. The premium baseline is sampled
  too, so a real "saved" figure is available.
- A few other tasks are seeded lightly, so the policy view shows several learned
  task types and the feed/time-series look populated.
- The near-duplicate cache is pre-warmed with one prompt, so a paraphrase of it
  hits (semantically, when an embedding provider is configured).
"""
import random
import time

# The math task: the whole pool, so routing exploits rather than explores.
# (model, quality, cost_per_call). tokens are fixed at 100 so unit price is
# well-defined and the price-shift detector is armed.
ARBITRAGE_TASK = "math"
ARBITRAGE_MODEL = "deepseek-chat-v3"                    # cheapest good -> the current pick
FALLBACK_MODEL = "mistral-small-3.2-24b-instruct-2506"  # next-cheapest good -> re-route target

# Costs are the runtime's real measured per-call charges for a short math prompt,
# so the learned state matches reality and the re-route lands on a genuinely
# cheaper model. Free models are given a lower math quality so the paid pick wins.
_MATH = [
    ("deepseek-chat-v3", 0.93, 3e-6),                     # chosen (cheapest good)
    ("mistral-small-3.2-24b-instruct-2506", 0.94, 4e-6),  # fallback (2nd cheapest good)
    ("gpt-4.1-mini", 0.90, 9e-6),
    ("llama-3.1-70b-instruct", 0.91, 1.3e-5),
    ("gemini-2.5-flash", 0.90, 1.5e-5),
    ("gpt-4.1", 0.95, 6e-5),
    ("gemini-2.5-pro", 0.95, 7e-5),
    ("gpt-4o", 0.96, 8.8e-5),                             # premium baseline
    ("gpt-4o-mini", 0.94, 1.15e-4),
    ("deepseek-v4-flash", 0.70, 0.0),
    ("deepseek-v4-pro", 0.72, 0.0),
    ("llama-3.3-70b-instruct", 0.70, 0.0),
    ("qwen3-coder-480b-a35b-07-25", 0.68, 0.0),
    ("hermes-3-llama-3.1-405b", 0.70, 0.0),
]
_MATH_SAMPLES = 12   # enough that the seeded quality outweighs the benchmark prior

# Other task types, seeded lightly for a learned-looking dashboard: each has a
# cheap/free model it routes to plus the premium baseline for a savings anchor.
# (task, chosen_model, chosen_quality, chosen_cost)
_OTHER = [
    ("code", "qwen3-coder-480b-a35b-07-25", 0.90, 0.0),
    ("structured", "deepseek-v4-flash", 0.92, 0.0),
    ("factual", "deepseek-v4-flash", 0.90, 0.0),
    ("open", "hermes-3-llama-3.1-405b", 0.88, 0.0),
]
_BASELINE_COST = 4e-5   # what the premium baseline costs on these tasks

# The prompt pre-loaded into the cache; a paraphrase of it will hit on stage.
CACHE_PROMPT = "What is the capital of France"
CACHE_ANSWER = "The capital of France is Paris."


def _completion_body(text: str, model: str) -> dict:
    return {
        "id": "chatcmpl_demo",
        "object": "chat.completion",
        "model": model,
        "choices": [{"index": 0, "finish_reason": "stop",
                     "message": {"role": "assistant", "content": text}}],
        "usage": {"total_tokens": 12},
    }


async def seed(state) -> dict:
    """Reset, then install the scripted demo state. Returns a short summary."""
    policy = state.policy
    policy.reset()
    policy.clear_metrics()
    state.price_mult.clear()
    state.quarantine.clear()
    state.cache.clear()

    # 1. The math arbitrage scenario: the full pool, so it exploits.
    for model, q, cost in _MATH:
        for _ in range(_MATH_SAMPLES):
            policy.record(ARBITRAGE_TASK, model, q, cost, tokens=100)

    # 2. A few other learned task types (chosen model + premium baseline).
    for task, model, q, cost in _OTHER:
        for _ in range(8):
            policy.record(task, model, q, cost, tokens=80)
        for _ in range(4):
            policy.record(task, "gpt-4o", 0.95, _BASELINE_COST, tokens=80)

    # 3. Backfill a realistic feed + counters + time series over the last ~12h.
    now = time.time()
    rng = random.Random(7)
    tasks = ["math", "code", "structured", "factual", "open"]
    picks = {"math": ARBITRAGE_MODEL, "code": "qwen3-coder-480b-a35b-07-25",
             "structured": "deepseek-v4-flash", "factual": "deepseek-v4-flash",
             "open": "hermes-3-llama-3.1-405b"}
    events = []
    for _ in range(48):
        task = rng.choice(tasks)
        model = picks[task]
        cost = 5e-6 if task == "math" else 0.0
        events.append({
            "ts": now - rng.uniform(0, 12 * 3600),
            "task": task, "classified_by": rng.choice(["rules", "rules", "rules", "model"]),
            "model": model, "mode": rng.choice(["exploit", "exploit", "exploit", "explore"]),
            "quality": round(rng.uniform(0.85, 1.0), 3), "cost": cost,
            "saved": None, "failover_from": None,
        })
    for ev in sorted(events, key=lambda e: e["ts"]):
        policy.add_event(ev)
        policy.bump_counter(ev["classified_by"])

    # 4. Pre-warm the cache with one prompt (embedded, if a provider is set).
    vector = None
    if state.embedder is not None:
        vector = await state.embedder.embed(CACHE_PROMPT)
    state.cache.store(CACHE_PROMPT, {
        "body": _completion_body(CACHE_ANSWER, "deepseek-v4-flash"),
        "model": "deepseek-v4-flash", "quality": 0.95,
    }, vector=vector)

    report = policy.report()
    return {
        "status": "seeded",
        "arbitrage_task": ARBITRAGE_TASK,
        "routes_to": policy.choose(ARBITRAGE_TASK).model,
        "fallback": FALLBACK_MODEL,
        "task_types": len(policy.snapshot()),
        "feed_events": len(events),
        "saved_pct": report["saved_pct"],
        "cache_prewarmed": CACHE_PROMPT,
        "cache_mode": "semantic" if state.embedder is not None else "lexical",
    }
