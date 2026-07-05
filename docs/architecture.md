# Architecture

Arbiter is a small FastAPI service that speaks the OpenAI chat-completions
protocol on its front, and calls the BTL runtime on its back. Between the two it
runs a fixed pipeline that decides *which* model should answer, checks the
answer, and learns from the result.

This document is the map. For the reasoning behind each stage, see
[strategies.md](strategies.md); for the HTTP surface, see
[api-reference.md](api-reference.md).

## The pipeline

Every chat request flows through the same core stages (a cache check, budget and
latency filters, in-request failover and a confidence cascade wrap these - see the
lifecycle below):

```
  OpenAI-compatible request
            |
            v
  1. CLASSIFY    (classifier.py)      rules first; a free model when ambiguous
                                      -> task type: code / math / structured / factual / open
            |
            v
  2. FILTER      (models.py: fits)    drop any model whose context cannot hold the
                                      prompt -> the eligible set
            |
            v
  3. ROUTE       (policy.py: choose)  explore new models, else exploit the cheapest
                                      one within tolerance of the best
            |
            v
  4. CALL        (btl.py: chat)       send the chosen model to the runtime; capture
                                      the answer and the cost headers
            |
            v
  5. GRADE       (scoring / judge)    objective check, or the judge for open-ended
                                      tasks -> a quality score from 0 to 1
            |
            v
  6. LEARN/REACT (policy.py: record)  fold cost and quality into the policy; a price
                                      move re-opens exploration
            |
            v
  answer + arbiter metadata
```

Stages 1-3 are free and fast (no model call, except the ambiguous-classify
case). The paid work is stage 4 - and, during exploration only, stage 5's judge.

## The request lifecycle, end to end

This is what happens for a single `POST /v1/chat/completions`, and where each
step lives in the code (`main.py:chat_completions` orchestrates it):

1. **Parse.** The request must contain `messages`. The `model` field the caller
   sent is intentionally ignored - choosing the model is Arbiter's job.
2. **Classify** (`classifier.py:classify_smart`). Rules bucket the request
   instantly; if none match, a free model reads it. Result: a task type plus how
   it was decided (`rules` / `model` / `model-fallback`).
3. **Cache check** (`cache.py`). If this prompt is a near-duplicate of a
   previously well-scored one (by embedding similarity, or lexical overlap), its
   stored answer is returned immediately, for free - no routing, no model call.
4. **Filter** (`models.py:fits`, plus the budget and latency gates). Keep only
   models whose context window fits the prompt, whose estimated cost is within any
   `arbiter_max_cost`, and whose learned latency is within any
   `arbiter_max_latency`. These are correctness/eligibility guards, ahead of cost.
5. **Route** (`policy.py:choose`). Given the task (split by difficulty into its
   own bucket for hard prompts) and the eligible set, the policy returns a
   `Decision` - a model, a mode, and a human-readable reason.
6. **Call, with failover** (`btl.py:chat`). The chosen model is sent to the
   runtime. If it errors, that model is quarantined and the next-best live model
   is tried within the same request, up to `MAX_ATTEMPTS`.
7. **Grade, with cascade** (`scoring.py:score`, `judge.py:judge`). Objective tasks
   are checked directly; open-ended tasks are judged, but only while exploring. If
   an objective check says the cheap answer failed, the request escalates once to
   a stronger model and keeps the better answer.
8. **Learn / react** (`policy.py:record`). The measured cost, quality and latency
   are folded into the policy. A statistically significant move in the model's
   cost-per-token wipes its stats so it is re-priced and re-routed. Human 👍/👎 on
   the answer, if sent later, carries the most weight.
9. **Respond.** The original OpenAI response is returned, plus an `arbiter` block
   describing the decision, quality, cost, latency and cache status.

## Component map

| File | Responsibility |
|------|----------------|
| `main.py` | FastAPI app; orchestrates the lifecycle above; owns the HTTP endpoints, failover, the confidence cascade, and the cache check. |
| `config.py` | Loads settings from `.env` / environment (key, base URL, baseline model, timeout, embedding provider). |
| `btl.py` | The only place that calls the runtime. `BTLClient.chat` plus the `Cost` and `Completion` value objects. |
| `classify.py` | Deterministic rule-based classification and the shared text helpers. |
| `classifier.py` | The hybrid classifier: rules first, then a free model on ambiguity. |
| `difficulty.py` | A free read of prompt difficulty; hard prompts route in their own sub-bucket. |
| `models.py` | The candidate model registry, the baseline, context windows, prices, and the `fits` guard. |
| `priors.py` | Public-benchmark quality priors that warm-start routing per task. |
| `scoring.py` | Objective quality checks for code, math, and structured tasks. |
| `judge.py` | LLM-as-judge for open-ended and factual tasks. |
| `cache.py` | The near-duplicate response cache (embedding similarity, or lexical fallback). |
| `embeddings.py` | Optional client for an external embedding provider, used by the cache. |
| `policy.py` | The routing brain and persistent memory (SQLite): `choose`, `record`, `report`, latency, feedback, and the durable feed/alerts/counters. |
| `static/index.html` | The fallback single-file dashboard, served at `/` when the web app has not been built. |
| `ui/` | The Next.js web app (landing, onboarding, dashboard, docs); exported to static files and served by FastAPI. See [interface.md](interface.md). |
| `scripts/bench.py` | A workload generator for demos and testing. |

## State and persistence

Arbiter keeps two kinds of state:

- **Durable - on disk, shared, persistent.** In a single SQLite database
  (`data/arbiter.db`): the per-task, per-model quality/cost/latency stats, human
  feedback, client keys and usage, and the observability tables - the
  recent-decisions feed, price-shift alerts, and classifier counters. There is one
  shared brain; every request reads and writes it regardless of session, and it
  all survives restarts. There is no per-user or per-session isolation.
- **Ephemeral - in memory.** Only a few things reset on restart: the near-duplicate
  cache, the model quarantine set, and the demo price multipliers, all in
  `app.state`.

## Where Arbiter touches the runtime

BTL is load-bearing in four distinct places, not one:

1. **Answering requests** - the routed model call (`btl.py:chat`).
2. **Classifying** - the free model used for ambiguous prompts
   (`classifier.py`).
3. **Judging** - the quality rater for open-ended tasks, during exploration
   (`judge.py`).
4. **Measuring and reacting to cost** - the `x-btl-*` headers drive both the
   savings figures and the price-shift detector (`btl.py:Cost`,
   `policy.py:record`).

Every one of these runs through a single BTL key on the `/v1/chat/completions`
surface. The one component that reaches *off* the runtime is the optional semantic
cache, which calls an external embedding provider (`embeddings.py`); with none
configured, even that stays local. The reasoning behind each is in
[strategies.md](strategies.md).
