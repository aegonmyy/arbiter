"""The pool of models Arbiter is allowed to route to.

Every id here has been checked against the runtime on the /v1/chat/completions
surface and returns a completion. Claude and other anthropic-direct models are
intentionally left out: they only answer on the /v1/messages surface, which is
a separate route we can add later.

The `tier` is a rough prior on how strong/expensive a model is. It only seeds
the exploration order - the real cost and quality numbers come from the runtime
at request time and are what the policy actually learns from.
"""
from dataclasses import dataclass

from . import config


@dataclass(frozen=True)
class ModelSpec:
    id: str
    tier: str        # "small" | "mid" | "large"
    context: int     # max context window in tokens
    in_price: float  # USD per 1M input tokens (runtime list price)
    out_price: float  # USD per 1M output tokens


# Curated spread across cost tiers. Kept small on purpose so exploring a new
# task type stays cheap. `context` lets us rule a model out before routing when
# a prompt won't fit; the prices let us rule one out when it would exceed a
# per-request budget. Both are guards that run ahead of the cost/quality
# decision. Prices are the runtime's list prices ($/1M tokens).
CANDIDATES: list[ModelSpec] = [
    ModelSpec("mistral-small-3.2-24b-instruct-2506", "small", 128_000, 0.075, 0.20),
    ModelSpec("deepseek-chat-v3", "small", 128_000, 0.20, 0.80),
    ModelSpec("llama-3.1-70b-instruct", "small", 131_072, 0.40, 0.40),
    ModelSpec("gpt-4.1-mini", "small", 1_047_576, 0.40, 1.60),
    ModelSpec("gemini-2.5-flash", "mid", 1_048_576, 0.30, 2.50),
    ModelSpec("gpt-4o-mini", "mid", 128_000, 0.15, 0.60),
    ModelSpec("gpt-4.1", "mid", 1_047_576, 2.00, 8.00),
    ModelSpec("gemini-2.5-pro", "large", 1_048_576, 1.25, 10.0),
]

# What a naive team would use for everything. Savings are measured against this.
# Driven by config so it can be pointed at a different premium model. Prices are
# gpt-4o's; update them if you change BASELINE_MODEL.
BASELINE = ModelSpec(config.BASELINE_MODEL, "large", config.BASELINE_CONTEXT, 2.50, 10.0)

CANDIDATE_IDS = [m.id for m in CANDIDATES]

_CONTEXT = {m.id: m.context for m in CANDIDATES} | {BASELINE.id: BASELINE.context}
_PRICE = {m.id: (m.in_price, m.out_price) for m in CANDIDATES} | {
    BASELINE.id: (BASELINE.in_price, BASELINE.out_price)
}


def context_of(model_id: str) -> int:
    return _CONTEXT.get(model_id, 0)


def fits(model_id: str, tokens_needed: int) -> bool:
    return context_of(model_id) >= tokens_needed


def estimate_cost(model_id: str, in_tokens: int, out_tokens: int) -> float:
    """Estimated USD cost of one call, from the runtime's list prices. Used by
    the per-request budget filter (the measured cost still comes from headers)."""
    ip, op = _PRICE.get(model_id, (0.0, 0.0))
    return (in_tokens * ip + out_tokens * op) / 1_000_000


def is_known(model_id: str) -> bool:
    return model_id == BASELINE.id or model_id in CANDIDATE_IDS
