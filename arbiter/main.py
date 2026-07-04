import json
import time
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .auth import require_client
from .btl import BTLClient, Cost
from .classify import _last_user_text
from .classifier import classify_smart
from .judge import judge
from .models import BASELINE, CANDIDATES, estimate_cost, fits
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


@app.post("/v1/register")
async def register(request: Request) -> dict:
    """Mint a client API key in exchange for an email. Open (no auth)."""
    body = await request.json()
    email = (body.get("email") or "").strip()
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(422, "a valid email is required")
    key = request.app.state.policy.register_key(email)
    return {"api_key": key}


@app.get("/v1/key")
async def key_info(request: Request, client_key: str = Depends(require_client)) -> dict:
    """Info and usage for the calling key."""
    if client_key in config.ARBITER_API_KEYS:
        return {"email": None, "status": "operator",
                "used_6h": 0, "limit_6h": None, "used_week": 0, "limit_week": None}
    info = request.app.state.policy.key_info(client_key)
    if not info:
        raise HTTPException(404, "key not found")
    return info


@app.post("/v1/key/{action}")
async def key_action(action: str, request: Request, client_key: str = Depends(require_client)) -> dict:
    """Pause, resume or revoke the calling key."""
    status = {"pause": "paused", "resume": "active", "revoke": "revoked"}.get(action)
    if status is None:
        raise HTTPException(404, "unknown action")
    if client_key in config.ARBITER_API_KEYS:
        raise HTTPException(400, "operator keys cannot be changed here")
    request.app.state.policy.set_key_status(client_key, status)
    return {"status": status}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request, client_key: str = Depends(require_client)):
    """OpenAI-compatible entry point that routes instead of passing through.

    We classify the request, let the policy pick a model, send it to the
    runtime, then score the answer and feed quality + measured cost back into
    the policy so the next similar request is routed better.
    """
    # Minted keys can be paused and are rate-limited (operator keys are exempt).
    if client_key not in config.ARBITER_API_KEYS:
        if request.app.state.policy.key_status(client_key) == "paused":
            raise HTTPException(403, detail={"error": "key_paused", "message": "This API key is paused. Resume it to route again."})
        ok, limit, retry = request.app.state.policy.try_use(client_key)
        if not ok:
            raise HTTPException(
                status_code=429,
                detail={"error": "rate_limited", "limit": limit, "retry_after_seconds": retry},
                headers={"Retry-After": str(retry)},
            )

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
    in_tokens = chars // 4
    out_tokens = int(payload.get("max_tokens", 512))
    tokens_needed = in_tokens + out_tokens
    eligible = [m for m in ALL_MODELS if fits(m, tokens_needed)]

    # Optional per-request budget ceiling (USD). Estimate each model's cost for
    # this request from list prices and keep only those within budget. This is a
    # non-standard field, so pop it before the payload goes to the runtime.
    max_cost = payload.pop("arbiter_max_cost", None)
    budget_met = None
    if max_cost is not None:
        try:
            max_cost = float(max_cost)
        except (TypeError, ValueError):
            max_cost = None
    if max_cost is not None and eligible:
        within = [m for m in eligible if estimate_cost(m, in_tokens, out_tokens) <= max_cost]
        budget_met = bool(within)
        # If nothing fits the budget, fall back to the single cheapest estimate.
        eligible = within or [min(eligible, key=lambda m: estimate_cost(m, in_tokens, out_tokens))]

    decision = policy.choose(task.value, allowed=eligible)

    # The client's requested model is ignored on purpose - choosing the model
    # is the whole point of Arbiter. We keep every other parameter as-is.
    payload["model"] = decision.model
    prompt = _last_user_text(messages)

    if payload.get("stream"):
        return _stream(request, payload, task, decision, classified_by, eligible, prompt)

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
        "budget_max_cost": max_cost,
        "budget_met": budget_met,
    }
    return body


def _stream(request: Request, payload, task, decision, classified_by, eligible, prompt):
    """Proxy a streaming completion. Tokens flow to the client live; the answer
    is scored and folded into the policy once the stream finishes."""
    app_state = request.app.state
    btl = app_state.btl
    policy = app_state.policy

    async def gen():
        full: list[str] = []
        usage_tokens = 0
        cost = Cost()
        try:
            async with btl.stream(payload) as resp:
                if resp.status_code != 200:
                    detail = (await resp.aread()).decode("utf-8", "replace")[:400]
                    yield f'data: {json.dumps({"error": {"upstream_status": resp.status_code, "detail": detail, "model": decision.model}})}\n\n'
                    return
                cost = Cost.from_headers(resp.headers)
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data.strip() != "[DONE]":
                            try:
                                chunk = json.loads(data)
                                choices = chunk.get("choices") or [{}]
                                delta = (choices[0].get("delta") or {}).get("content")
                                if delta:
                                    full.append(delta)
                                if chunk.get("usage"):
                                    usage_tokens = chunk["usage"].get("total_tokens", 0) or 0
                            except Exception:
                                pass
                    yield line + "\n"
        except httpx.RequestError as e:
            yield f'data: {json.dumps({"error": {"detail": f"unreachable: {type(e).__name__}"}})}\n\n'
            return

        # The client already has the full answer; now score it and learn.
        text = "".join(full)
        quality = score(task, prompt, text)
        if not quality.objective:
            if decision.mode == "explore":
                q = await judge(btl, prompt, text)
                quality = Score(q, "judged by model", objective=False)
            else:
                learned = policy.quality_of(task.value, decision.model)
                if learned is not None:
                    quality = Score(learned, "learned quality", objective=False)

        # The runtime does not report cost on streaming responses, so when the
        # header is absent we price the call at the model's learned average cost
        # (measured from non-streaming calls) and skip price-shift detection.
        estimated = cost.charged is None
        base = policy.cost_of(task.value, decision.model) or 0.0 if estimated else cost.charged
        c = (base or 0.0) * app_state.price_mult.get(decision.model, 1.0)
        shift = policy.record(task.value, decision.model, quality.value, c,
                              0 if estimated else usage_tokens)
        if shift:
            app_state.alerts.appendleft({**shift, "ts": time.time()})
        baseline_cost = policy.baseline_cost(task.value)
        saved = round(baseline_cost - c, 8) if baseline_cost is not None else None
        app_state.recent.appendleft({
            "ts": time.time(), "task": task.value, "classified_by": classified_by,
            "model": decision.model, "mode": decision.mode,
            "quality": round(quality.value, 3), "cost": c, "saved": saved,
        })
        # Trailing metadata event; strict OpenAI clients stop at [DONE] and ignore it.
        meta = {"task": task.value, "model": decision.model, "mode": decision.mode,
                "classified_by": classified_by, "quality": round(quality.value, 3),
                "cost": c, "cost_estimated": estimated, "saved": saved}
        yield f"event: arbiter\ndata: {json.dumps(meta)}\n\n"

    headers = {
        "X-Arbiter-Model": decision.model,
        "X-Arbiter-Task": task.value,
        "X-Arbiter-Mode": decision.mode,
        "X-Arbiter-Classified-By": classified_by,
        "X-Arbiter-Eligible": str(len(eligible)),
        "Cache-Control": "no-cache",
    }
    return StreamingResponse(gen(), media_type="text/event-stream", headers=headers)


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


@app.get("/v1/pricing")
async def pricing(request: Request) -> list:
    """The runtime's full chat-surface catalog with list prices, each tagged
    whether Arbiter routes to it. Lets a client preview the whole market at a
    budget while routing stays within the curated pool. Cached after first call."""
    st = request.app.state
    if getattr(st, "catalog", None):
        return st.catalog

    routable = {m.id for m in CANDIDATES} | {BASELINE.id}
    catalog: list[dict] = []
    try:
        data = await st.btl.models()
        for m in data.get("data", []):
            if "/v1/chat/completions" not in (m.get("compatible_endpoints") or []):
                continue
            bp = m.get("benchmark_pricing") or {}
            i, o = bp.get("input_per_mtok_min"), bp.get("output_per_mtok_min")
            if i is None or o is None:
                continue
            catalog.append({
                "id": m["id"], "in_price": i, "out_price": o,
                "context": m.get("context_window", 0), "routable": m["id"] in routable,
            })
    except Exception:
        pass

    if not catalog:  # runtime unreachable: fall back to the routable pool
        for m in list(CANDIDATES) + [BASELINE]:
            catalog.append({"id": m.id, "in_price": m.in_price, "out_price": m.out_price,
                            "context": m.context, "routable": True})

    catalog.sort(key=lambda r: r["in_price"] + r["out_price"])
    st.catalog = catalog
    return catalog


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


@app.post("/v1/simulate-price", dependencies=[Depends(require_client)])
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


@app.post("/v1/reset", dependencies=[Depends(require_client)])
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
