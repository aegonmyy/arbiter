"""Score how good an answer is, on a 0..1 scale.

The router can only prefer a cheaper model if it can tell whether that model
actually did the job. Where a task has an objective check we use it - those
signals are free and trustworthy. For open-ended tasks there's no ground truth,
so we fall back to a judge model (one strong model rating the answer), and if no
judge is wired in we stay neutral rather than guess.
"""
import ast
import json
import re
from dataclasses import dataclass

from .classify import TaskType


@dataclass
class Score:
    value: float          # 0..1
    reason: str
    objective: bool       # True if grounded in a real check, not a judge/guess


_CODE_BLOCK = re.compile(r"```(?:[a-zA-Z0-9_+-]*)\n(.*?)```", re.DOTALL)
_JSON_CANDIDATE = re.compile(r"(\{.*\}|\[.*\])", re.DOTALL)


# Tokens that suggest a bare (unfenced) answer is actually code rather than prose.
_CODE_ISH = re.compile(r"[{}();=]|\b(def|class|return|import|function|const|let|var)\b")


def _extract_code(answer: str) -> str | None:
    m = _CODE_BLOCK.search(answer)
    if m:
        return m.group(1).strip()
    # No fence: only treat it as code if it actually looks like code, so a
    # plain-English non-answer doesn't get credit for "almost parsing".
    stripped = answer.strip()
    if stripped and _CODE_ISH.search(stripped):
        return stripped
    return None


def score_code(answer: str) -> Score:
    code = _extract_code(answer)
    if not code:
        return Score(0.1, "no code found", objective=True)
    try:
        ast.parse(code)
    except SyntaxError as e:
        return Score(0.4, f"code present but does not parse: {e.msg}", objective=True)
    # Parses cleanly and is non-trivial.
    substance = 0.15 if len(code.splitlines()) > 1 else 0.0
    return Score(min(1.0, 0.85 + substance), "code parses", objective=True)


def score_math(prompt: str, answer: str) -> Score:
    """If the prompt is a plain arithmetic expression we can evaluate it and
    check the answer contains the right number."""
    expr = re.search(r"[-+*/^().\d\s]{3,}", prompt)
    expected = None
    if expr:
        candidate = expr.group(0).replace("^", "**").strip()
        if re.search(r"\d", candidate) and re.search(r"[-+*/]", candidate):
            try:
                expected = eval(candidate, {"__builtins__": {}}, {})  # arithmetic only
            except Exception:
                expected = None
    if expected is None:
        return Score(0.5, "no checkable expression", objective=False)

    numbers = re.findall(r"-?\d+(?:\.\d+)?", answer.replace(",", ""))
    hit = any(abs(float(n) - float(expected)) < 1e-6 for n in numbers)
    return Score(1.0 if hit else 0.0,
                 f"expected {expected}, {'found' if hit else 'missing'}",
                 objective=True)


def score_structured(answer: str) -> Score:
    m = _JSON_CANDIDATE.search(answer)
    if not m:
        return Score(0.2, "no JSON-like content", objective=True)
    try:
        json.loads(m.group(1))
    except json.JSONDecodeError:
        return Score(0.45, "JSON present but invalid", objective=True)
    return Score(1.0, "valid JSON", objective=True)


def score(task: TaskType, prompt: str, answer: str) -> Score:
    """Objective scoring only. Open/factual tasks return a neutral,
    non-objective score here; the LLM judge (see judge.py) handles those."""
    answer = (answer or "").strip()
    if not answer:
        return Score(0.0, "empty answer", objective=True)
    if task == TaskType.CODE:
        return score_code(answer)
    if task == TaskType.MATH:
        return score_math(prompt, answer)
    if task == TaskType.STRUCTURED:
        return score_structured(answer)
    return Score(0.5, "no objective check for this task type", objective=False)
