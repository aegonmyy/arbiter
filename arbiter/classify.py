"""Bucket a request into a task type.

Routing is learned per task type, so this is the key that everything hangs off
of. It's deliberately a cheap, deterministic heuristic: no extra model call on
the hot path, and it's easy to reason about. If a bucket turns out to be too
coarse we can split it later, or swap in a small classifier model.
"""
import re
from enum import Enum


class TaskType(str, Enum):
    CODE = "code"
    MATH = "math"
    STRUCTURED = "structured"
    FACTUAL = "factual"
    OPEN = "open"


_CODE_HINTS = re.compile(
    r"```|\b(def |class |function |import |const |public static|"
    r"write (a|the|some)? ?(code|function|script|program)|"
    r"implement|refactor|debug|stack trace|compile|regex)\b",
    re.IGNORECASE,
)
_STRUCTURED_HINTS = re.compile(
    r"\b(json|yaml|csv|schema|table|as a list|bullet points|"
    r"key-value|valid json|return an? (object|array))\b",
    re.IGNORECASE,
)
_MATH_HINTS = re.compile(
    r"\b(calculate|compute|solve|derivative|integral|probability|"
    r"how much is|what is \d|sum of|equation)\b|[\d)]\s*[-+*/^]\s*\d",
    re.IGNORECASE,
)
_FACTUAL_HINTS = re.compile(
    r"^\s*(who|what|when|where|which|how many|name the|list the)\b",
    re.IGNORECASE,
)


def _last_user_text(messages: list[dict]) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, list):  # OpenAI content-parts form
                content = " ".join(
                    p.get("text", "") for p in content if isinstance(p, dict)
                )
            return content or ""
    return ""


def classify(messages: list[dict]) -> TaskType:
    text = _last_user_text(messages)

    # Order matters: code and structured are the most distinctive, so check
    # them first. Short question-shaped prompts fall through to factual, and
    # anything else is treated as open-ended generation.
    if _CODE_HINTS.search(text):
        return TaskType.CODE
    if _STRUCTURED_HINTS.search(text):
        return TaskType.STRUCTURED
    if _MATH_HINTS.search(text):
        return TaskType.MATH
    if _FACTUAL_HINTS.search(text) and len(text) < 200:
        return TaskType.FACTUAL
    return TaskType.OPEN
