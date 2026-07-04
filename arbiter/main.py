import time
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse

from .btl import BTLClient
from .classify import classify, _last_user_text
from .judge import judge
from .models import fits
from .policy import ALL_MODELS, Policy
from .scoring import Score, score

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.btl = BTLClient()
    app.state.policy = Policy()
    # Small ring buffer of recent routing decisions, for the live dashboard feed.
    app.state.recent = deque(maxlen=25)
    yield
    await app.state.btl.aclose()


app = FastAPI(title="Arbiter", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """OpenAI-compatible entry point that routes instead of passing through.

    We classify the request, let the policy pick a model, send it to the
    runtime, then score the answer and feed quality + measured cost back into
    the policy so the next similar request is routed better.
    """
    payload = await request.json()
    if "messages" not in payload:
        raise HTTPException(422, "request must include 'messages'")

    policy: Policy = request.app.state.policy
    messages = payload["messages"]
    task = classify(messages)

    # Capability guard: only consider models whose context window fits this
    # prompt (rough 4-chars-per-token estimate plus the requested reply room).
    chars = sum(len(str(m.get("content", ""))) for m in messages)
    tokens_needed = chars // 4 + int(payload.get("max_tokens", 512))
    eligible = [m for m in ALL_MODELS if fits(m, tokens_needed)]

    decision = policy.choose(task.value, allowed=eligible)

    # The client's requested model is ignored on purpose — choosing the model
    # is the whole point of Arbiter. We keep every other parameter as-is.
    payload["model"] = decision.model
    completion = await request.app.state.btl.chat(payload)

    prompt = _last_user_text(messages)
    quality = score(task, prompt, completion.text)

    # For tasks with no objective check, get a real quality signal from the
    # judge — but only while exploring. Once we've learned a model's quality,
    # exploitation reuses it so steady-state traffic stays cheap.
    if not quality.objective:
        if decision.mode == "explore":
            q = await judge(request.app.state.btl, prompt, completion.text)
            quality = Score(q, "judged by model", objective=False)
        else:
            learned = policy.quality_of(task.value, decision.model)
            if learned is not None:
                quality = Score(learned, "learned quality", objective=False)

    cost = completion.cost.charged or 0.0
    policy.record(task.value, decision.model, quality.value, cost)

    baseline_cost = policy.baseline_cost(task.value)
    saved = round(baseline_cost - cost, 8) if baseline_cost is not None else None

    request.app.state.recent.appendleft({
        "ts": time.time(),
        "task": task.value,
        "model": decision.model,
        "mode": decision.mode,
        "quality": round(quality.value, 3),
        "cost": cost,
        "saved": saved,
    })

    body = completion.body
    body["arbiter"] = {
        "task": task.value,
        "model": decision.model,
        "mode": decision.mode,
        "reason": decision.reason,
        "quality": round(quality.value, 3),
        "quality_reason": quality.reason,
        "cost": cost,
        "baseline_cost": baseline_cost,
        "saved": saved,
        "tokens_needed": tokens_needed,
        "eligible_models": len(eligible),
    }
    return body


@app.get("/v1/report")
async def report(request: Request) -> dict:
    """Cumulative savings vs. always using the baseline model."""
    return request.app.state.policy.report()


@app.get("/v1/policy")
async def policy_state(request: Request) -> dict:
    """What the router has learned per task type so far."""
    return request.app.state.policy.snapshot()


@app.get("/v1/recent")
async def recent(request: Request) -> list:
    """The most recent routing decisions, newest first."""
    return list(request.app.state.recent)


@app.post("/v1/reset")
async def reset(request: Request) -> dict:
    """Clear learned state and the decision feed for a fresh demo run."""
    request.app.state.policy.reset()
    request.app.state.recent.clear()
    return {"status": "reset"}


@app.get("/")
async def dashboard() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
