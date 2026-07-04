import time
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .btl import BTLClient
from .classify import _last_user_text
from .classifier import classify_smart
from .judge import judge
from .models import fits
from .policy import ALL_MODELS, Policy
from .scoring import Score, score

STATIC_DIR = Path(__file__).resolve().parent / "static"
# The exported Next.js UI, if it has been built (docs + rich dashboard).
UI_OUT = Path(__file__).resolve().parent.parent / "ui" / "out"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.btl = BTLClient()
    app.state.policy = Policy()
    # Small ring buffer of recent routing decisions, for the live dashboard feed.
    app.state.recent = deque(maxlen=25)
    # Price-shift alerts, and a demo multiplier to simulate a provider re-price.
    app.state.alerts = deque(maxlen=25)
    app.state.price_mult = {}
    # How each request's task type was decided.
    app.state.classifier_counts = {"rules": 0, "model": 0, "model-fallback": 0}
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
    task, classified_by = await classify_smart(request.app.state.btl, messages)
    counts = request.app.state.classifier_counts
    counts[classified_by] = counts.get(classified_by, 0) + 1

    # Capability guard: only consider models whose context window fits this
    # prompt (rough 4-chars-per-token estimate plus the requested reply room).
    chars = sum(len(str(m.get("content", ""))) for m in messages)
    tokens_needed = chars // 4 + int(payload.get("max_tokens", 512))
    eligible = [m for m in ALL_MODELS if fits(m, tokens_needed)]

    decision = policy.choose(task.value, allowed=eligible)

    # The client's requested model is ignored on purpose - choosing the model
    # is the whole point of Arbiter. We keep every other parameter as-is.
    payload["model"] = decision.model
    try:
        completion = await request.app.state.btl.chat(payload)
    except httpx.HTTPStatusError as e:
        # The runtime/provider rejected the call (e.g. 402 out of credit, 429
        # rate limit, 400 bad request). Surface it cleanly with the upstream
        # status and don't record a failed attempt into the policy.
        try:
            detail = e.response.json()
        except ValueError:
            detail = (e.response.text or "")[:300]
        raise HTTPException(status_code=e.response.status_code,
                            detail={"upstream": "btl_runtime", "model": decision.model, "error": detail})
    except httpx.RequestError as e:
        raise HTTPException(status_code=502,
                            detail={"upstream": "btl_runtime", "error": f"unreachable: {type(e).__name__}"})

    prompt = _last_user_text(messages)
    quality = score(task, prompt, completion.text)

    # For tasks with no objective check, get a real quality signal from the
    # judge - but only while exploring. Once we've learned a model's quality,
    # exploitation reuses it so steady-state traffic stays cheap.
    if not quality.objective:
        if decision.mode == "explore":
            q = await judge(request.app.state.btl, prompt, completion.text)
            quality = Score(q, "judged by model", objective=False)
        else:
            learned = policy.quality_of(task.value, decision.model)
            if learned is not None:
                quality = Score(learned, "learned quality", objective=False)

    # Real charge from the runtime, optionally scaled by the demo multiplier so
    # a price change can be simulated on cue.
    raw_cost = completion.cost.charged or 0.0
    cost = raw_cost * request.app.state.price_mult.get(decision.model, 1.0)
    tokens = (completion.body.get("usage") or {}).get("total_tokens", 0)

    shift = policy.record(task.value, decision.model, quality.value, cost, tokens)
    if shift:
        request.app.state.alerts.appendleft({**shift, "ts": time.time()})

    baseline_cost = policy.baseline_cost(task.value)
    saved = round(baseline_cost - cost, 8) if baseline_cost is not None else None

    request.app.state.recent.appendleft({
        "ts": time.time(),
        "task": task.value,
        "classified_by": classified_by,
        "model": decision.model,
        "mode": decision.mode,
        "quality": round(quality.value, 3),
        "cost": cost,
        "saved": saved,
    })

    body = completion.body
    body["arbiter"] = {
        "task": task.value,
        "classified_by": classified_by,
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


@app.get("/v1/overview")
async def overview(request: Request) -> dict:
    """Summary stats for the dashboard beyond raw savings."""
    st = request.app.state
    return {
        "pool_size": len(ALL_MODELS),
        "classifier": dict(st.classifier_counts),
        "alerts": len(st.alerts),
        "active_price_overrides": st.price_mult,
    }


@app.get("/v1/alerts")
async def alerts(request: Request) -> list:
    """Recent price-shift events that forced a model to be re-learned."""
    return list(request.app.state.alerts)


@app.post("/v1/simulate-price")
async def simulate_price(request: Request) -> dict:
    """Demo hook: scale a model's reported cost to imitate a provider re-price.

    Body: {"model": "deepseek-chat-v3", "multiplier": 3.0}. Set multiplier back
    to 1 to clear it. Lets us show the router reacting to a price move live.
    """
    body = await request.json()
    model = body.get("model")
    mult = float(body.get("multiplier", 1.0))
    if not model:
        raise HTTPException(422, "body must include 'model'")
    if mult == 1.0:
        request.app.state.price_mult.pop(model, None)
    else:
        request.app.state.price_mult[model] = mult
    return {"model": model, "multiplier": mult, "active": request.app.state.price_mult}


@app.post("/v1/reset")
async def reset(request: Request) -> dict:
    """Clear learned state and the decision feed for a fresh demo run."""
    request.app.state.policy.reset()
    request.app.state.recent.clear()
    request.app.state.alerts.clear()
    request.app.state.price_mult.clear()
    for k in request.app.state.classifier_counts:
        request.app.state.classifier_counts[k] = 0
    return {"status": "reset"}


# Serve the UI last, so it never shadows the API routes above. If the Next.js
# app has been exported to ui/out, serve that (dashboard at / and docs at
# /docs); otherwise fall back to the built-in single-file dashboard.
if UI_OUT.is_dir():
    app.mount("/", StaticFiles(directory=str(UI_OUT), html=True), name="ui")
else:
    @app.get("/")
    async def dashboard() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")
