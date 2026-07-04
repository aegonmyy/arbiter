from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request

from .btl import BTLClient
from .classify import classify, _last_user_text
from .policy import Policy
from .scoring import score


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.btl = BTLClient()
    app.state.policy = Policy()
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
    decision = policy.choose(task.value)

    # The client's requested model is ignored on purpose — choosing the model
    # is the whole point of Arbiter. We keep every other parameter as-is.
    payload["model"] = decision.model
    completion = await request.app.state.btl.chat(payload)

    quality = score(task, _last_user_text(messages), completion.text)
    cost = completion.cost.charged or 0.0
    policy.record(task.value, decision.model, quality.value, cost)

    body = completion.body
    body["arbiter"] = {
        "task": task.value,
        "model": decision.model,
        "mode": decision.mode,
        "reason": decision.reason,
        "quality": round(quality.value, 3),
        "quality_reason": quality.reason,
        "cost": cost,
        "baseline_cost": policy.baseline_cost(task.value),
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
