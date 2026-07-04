"""LLM-as-judge for tasks with no objective check (open-ended, factual).

Code, math and structured answers get graded by a real check. Everything else
has no ground truth, so we ask one capable model to rate the answer. To keep
this from becoming a cost on every request, the caller only judges while it's
exploring a task type - once a model's quality is known, exploitation reuses
the learned number instead of paying for another judgement.
"""
import re

from .btl import BTLClient

JUDGE_MODEL = "gpt-4o"

_SYSTEM = (
    "You grade an assistant's answer. Rate from 0.0 to 1.0 how well the ANSWER "
    "responds to the REQUEST, considering accuracy, relevance and completeness. "
    "Reply with only a single number between 0 and 1."
)

_NUMBER = re.compile(r"[01](?:\.\d+)?")


# Grading only needs a sample of the text, not the whole thing. Capping the
# input keeps the judge cheap and stops a large prompt from overflowing the
# judge model's own context window.
_MAX_CHARS = 4000


async def judge(btl: BTLClient, request_text: str, answer: str,
                model: str = JUDGE_MODEL) -> float:
    if not answer.strip():
        return 0.0
    req = request_text[:_MAX_CHARS]
    ans = answer[:_MAX_CHARS]
    try:
        completion = await btl.chat({
            "model": model,
            "messages": [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": f"REQUEST:\n{req}\n\nANSWER:\n{ans}"},
            ],
            "max_tokens": 6,
            "temperature": 0,
        })
    except Exception:
        # A judge failure must never fail the user's request; stay neutral.
        return 0.5
    m = _NUMBER.search(completion.text)
    if not m:
        return 0.5
    return max(0.0, min(1.0, float(m.group(0))))
