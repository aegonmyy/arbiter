"""Hybrid task classification: fast rules first, a free model on doubt.

Clear-cut prompts (a code fence, `calculate 5*5`) are handled instantly by the
rules — no network call. Only when the rules can't tell do we ask a small free
model to read the prompt. If that call fails for any reason we fall back to
treating it as open-ended, so classification never breaks the request.

The model here (deepseek-v4-flash) is currently $0 per call on the runtime and,
unlike some free models, isn't a reasoning model — so it emits the answer word
directly instead of spending its budget thinking. If its price ever changes,
the price-shift machinery already notices; we route it through BTL like
everything else.
"""
from .btl import BTLClient
from .classify import TaskType, _last_user_text, rules_classify

CLASSIFIER_MODEL = "deepseek-v4-flash"

_SYSTEM = (
    "Classify the user's request into exactly one of these types: "
    "code, math, structured, factual, open. "
    "code = writing or debugging programs. math = arithmetic or calculation. "
    "structured = output in a specific format like JSON or a table. "
    "factual = a short question with a definite answer. "
    "open = anything open-ended. Reply with only the single type word."
)

_WORDS = {t.value: t for t in TaskType}


async def classify_smart(btl: BTLClient, messages: list[dict]) -> tuple[TaskType, str]:
    """Return (task, how) where how is 'rules', 'model', or 'model-fallback'."""
    hit = rules_classify(messages)
    if hit is not None:
        return hit, "rules"

    # Ambiguous — ask the free model.
    try:
        completion = await btl.chat({
            "model": CLASSIFIER_MODEL,
            "messages": [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": _last_user_text(messages)},
            ],
            "max_tokens": 8,
            "temperature": 0,
        })
        word = completion.text.strip().lower().split()[0] if completion.text.strip() else ""
        if word in _WORDS:
            return _WORDS[word], "model"
    except Exception:
        pass  # any failure -> safe default below

    return TaskType.OPEN, "model-fallback"
