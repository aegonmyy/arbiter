from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request

from .btl import BTLClient


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.btl = BTLClient()
    yield
    await app.state.btl.aclose()


app = FastAPI(title="Arbiter", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """OpenAI-compatible entry point.

    For now this is a straight passthrough to the runtime: whatever model the
    client asked for is what we send. The routing policy that picks a cheaper
    model lands on top of this in the next step — the important thing here is
    that a drop-in OpenAI client works unchanged and we capture the cost of
    every call.
    """
    payload = await request.json()
    if "model" not in payload or "messages" not in payload:
        raise HTTPException(422, "request must include 'model' and 'messages'")

    completion = await request.app.state.btl.chat(payload)

    # Surface the runtime's cost accounting back to the caller so it's visible
    # end to end, not just in our own logs.
    body = completion.body
    body.setdefault("arbiter", {})
    body["arbiter"]["cost"] = {
        "charged": completion.cost.charged,
        "saved": completion.cost.saved,
        "benchmark": completion.cost.benchmark,
        "cache_tier": completion.cost.cache_tier,
    }
    return body
