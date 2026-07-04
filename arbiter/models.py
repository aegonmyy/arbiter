"""The pool of models Arbiter is allowed to route to.

Every id here has been checked against the runtime on the /v1/chat/completions
surface and returns a completion. Claude and other anthropic-direct models are
intentionally left out: they only answer on the /v1/messages surface, which is
a separate route we can add later.

The `tier` is a rough prior on how strong/expensive a model is. It only seeds
the exploration order — the real cost and quality numbers come from the runtime
at request time and are what the policy actually learns from.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ModelSpec:
    id: str
    tier: str  # "small" | "mid" | "large"


# Curated spread across cost tiers. Kept small on purpose so exploring a new
# task type stays cheap.
CANDIDATES: list[ModelSpec] = [
    ModelSpec("mistral-small-3.2-24b-instruct-2506", "small"),
    ModelSpec("deepseek-chat-v3", "small"),
    ModelSpec("llama-3.1-70b-instruct", "small"),
    ModelSpec("gpt-4.1-mini", "small"),
    ModelSpec("gemini-2.5-flash", "mid"),
    ModelSpec("gpt-4o-mini", "mid"),
    ModelSpec("gpt-4.1", "mid"),
    ModelSpec("gemini-2.5-pro", "large"),
]

# What a naive team would use for everything. Savings are measured against this.
BASELINE = ModelSpec("gpt-4o", "large")

CANDIDATE_IDS = [m.id for m in CANDIDATES]


def is_known(model_id: str) -> bool:
    return model_id == BASELINE.id or model_id in CANDIDATE_IDS
