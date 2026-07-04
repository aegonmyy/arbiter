"""Warm-start quality priors from public benchmarks.

Cold start is expensive: with no data, the policy has to explore every model on
every new task type before it can exploit, and savings sit near zero while it
pays that "tuition". But we are not actually starting from zero knowledge -
these models have published benchmark results. This module seeds a per-model,
per-task quality prior from that public evidence so the router makes sensible
choices from the first request, then lets live measurements override it.

The prior is deliberately weak (see PRIOR_STRENGTH in policy.py): it is folded in
as a small number of pseudo-observations, so a couple of real calls outweigh it.
It anchors early, noisy estimates and then gets out of the way. The numbers are
approximate, rounded reads of well-known public benchmarks mapped onto our task
types - not exact scores, and not load-bearing once real data arrives:

    code       -> coding benchmarks (HumanEval / code-completion class)
    math       -> grade-school & competition math (GSM8K / MATH class)
    structured -> instruction-following / format-adherence (IFEval class)
    factual    -> knowledge QA (MMLU class)
    open       -> general chat quality (chat-arena / MT-bench class)

A model with no entry here simply has no prior and is learned purely from data.
"""
from .classify import TaskType

# model id -> {task value: prior quality in 0..1}
_PRIORS: dict[str, dict[str, float]] = {
    # --- frontier / premium ------------------------------------------------
    "gpt-4o": {"code": 0.90, "math": 0.86, "structured": 0.90, "factual": 0.88, "open": 0.90},
    "gpt-4.1": {"code": 0.92, "math": 0.88, "structured": 0.91, "factual": 0.89, "open": 0.90},
    "gemini-2.5-pro": {"code": 0.92, "math": 0.92, "structured": 0.90, "factual": 0.89, "open": 0.90},
    # --- strong mid --------------------------------------------------------
    "deepseek-v4-pro": {"code": 0.88, "math": 0.90, "structured": 0.87, "factual": 0.85, "open": 0.87},
    "gemini-2.5-flash": {"code": 0.86, "math": 0.87, "structured": 0.86, "factual": 0.84, "open": 0.85},
    "gpt-4.1-mini": {"code": 0.85, "math": 0.84, "structured": 0.86, "factual": 0.83, "open": 0.84},
    "deepseek-chat-v3": {"code": 0.85, "math": 0.85, "structured": 0.83, "factual": 0.82, "open": 0.83},
    "qwen3-coder-480b-a35b-07-25": {"code": 0.90, "math": 0.82, "structured": 0.84, "factual": 0.78, "open": 0.80},
    "hermes-3-llama-3.1-405b": {"code": 0.80, "math": 0.78, "structured": 0.82, "factual": 0.82, "open": 0.84},
    "llama-3.3-70b-instruct": {"code": 0.80, "math": 0.80, "structured": 0.82, "factual": 0.81, "open": 0.82},
    # --- small / cheap -----------------------------------------------------
    "deepseek-v4-flash": {"code": 0.80, "math": 0.82, "structured": 0.80, "factual": 0.76, "open": 0.78},
    "gpt-4o-mini": {"code": 0.78, "math": 0.75, "structured": 0.80, "factual": 0.76, "open": 0.79},
    "mistral-small-3.2-24b-instruct-2506": {"code": 0.74, "math": 0.72, "structured": 0.78, "factual": 0.72, "open": 0.76},
    "llama-3.1-70b-instruct": {"code": 0.76, "math": 0.74, "structured": 0.78, "factual": 0.78, "open": 0.79},
}


def prior_quality(task: str, model: str) -> float | None:
    """The published-benchmark quality prior for this model on this task, or None
    if we have no prior (the model is then learned purely from live data)."""
    return _PRIORS.get(model, {}).get(task)


def has_prior(model: str) -> bool:
    return model in _PRIORS


# Sanity: every task value we route on is a valid TaskType.
_VALID = {t.value for t in TaskType}
for _m, _d in _PRIORS.items():
    assert set(_d) <= _VALID, f"unknown task in prior for {_m}: {set(_d) - _VALID}"
