"""A cheap, deterministic read of how hard a single prompt is.

Task type alone is coarse: "what is 2+2" and "prove the infinitude of primes"
are both `math`, but they do not need the same model. Rather than learn a
separate policy for every prompt, we split each task into two difficulty tiers
and route them independently. To stay backward-compatible with everything the
router has already learned, only *hard* prompts get a new sub-bucket
(`math:hard`); easy prompts keep using the base task bucket. So the common,
easy case reuses existing learning and the hard case gets its own.

The signal is a handful of surface cues - length, multi-step/reasoning words,
several questions, and task-specific complexity markers. It never calls a model:
like classification, it must be free and run on every request.
"""
from .classify import TaskType

# Reasoning / multi-step cues that suggest a harder request, task-agnostic.
_HARD_CUES = (
    "step by step", "step-by-step", "prove", "derive", "explain why",
    "explain how", "in detail", "trade-off", "tradeoff", "edge case",
    "optimize", "optimise", "efficient", "complexity", "analyze", "analyse",
    "compare", "reason about", "justify", "walk through", "from scratch",
)
_CODE_HARD = ("class ", "async", "concurren", "thread", "benchmark", "o(n",
              "algorithm", "data structure", "recursion", "regex", "state machine")
_MATH_HARD = ("integral", "derivative", "matrix", "probability", "proof",
              "limit", "summation", "∑", "∫", "theorem", "equation")


def assess(task: TaskType, prompt: str) -> str:
    """Return "easy" or "hard" for this prompt within its task type."""
    text = prompt or ""
    low = text.lower()
    score = 0

    n = len(text)
    if n > 600:
        score += 2
    elif n > 250:
        score += 1

    score += sum(1 for c in _HARD_CUES if c in low)
    if low.count("?") >= 2:
        score += 1
    if task == TaskType.CODE and any(k in low for k in _CODE_HARD):
        score += 1
    if task == TaskType.MATH and any(k in low for k in _MATH_HARD):
        score += 1

    return "hard" if score >= 2 else "easy"


def route_key(task: TaskType, prompt: str) -> str:
    """The policy key for this request: the base task for easy prompts, a
    per-difficulty sub-bucket for hard ones."""
    return task.value if assess(task, prompt) == "easy" else f"{task.value}:hard"
