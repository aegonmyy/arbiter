# Arbiter

**A drop-in, OpenAI-compatible router that sends each request to the cheapest
model that still gets it right - and proves the savings from the runtime's own
billing headers.**

Point your existing OpenAI client at Arbiter, keep your code exactly as it is,
and it forwards each request to the [Bad Theory Labs runtime](https://runtime.badtheorylabs.com/docs),
choosing a model per request based on what actually works for that kind of task
and what it costs. It reads the runtime's `x-btl-*` cost headers on every
response, so savings are **measured, not guessed**.

## Quickstart

```bash
cp .env.example .env && $EDITOR .env    # add your GATEWAY_API_KEY (a BTL key)
./scripts/dev.sh                        # starts the proxy on :8000
```

Then change one line in your app - the base URL - and keep everything else:

```python
client = OpenAI(base_url="https://arbiter.ameenme.dev/v1", api_key="arb_...")
client.chat.completions.create(model="anything", messages=[...])  # model is ignored on purpose
```

## Why it needs BTL

> None of this works on a raw provider key. Arbiter routes **model choice**; the
> runtime routes **providers** and - crucially - **reports the real cost of every
> call** in a response header. That single signal is what turns "trust me, this
> saves money" into a measured number, and it's the same signal Arbiter consumes
> as a live control input to re-route when a model's price moves. One key also
> reaches ~300 models across providers, which is the pool Arbiter arbitrages
> over. Take away the runtime and both the measured savings and the price
> reaction disappear.

## How it works

```
  your OpenAI client
         │  POST /v1/chat/completions   (model field ignored)
         ▼
┌───────────────────────────────────────────────────────────────┐
│  ARBITER                                                        │
│                                                                 │
│  1. classify ──► task type            rules first, free model  │
│       │                                on ambiguity            │
│       ▼                                                         │
│  2. filter eligible models   context window ∙ budget ∙ live    │
│       │                                                         │
│       ▼                                                         │
│  3. policy.choose()          explore every candidate a few     │
│       │                      times, then exploit the cheapest  │
│       │                      model within tolerance of best q  │
│       ▼                                                         │
│  4. call model ──────────────────────────────────►  BTL runtime│
│       │  ◄───────── answer + x-btl-customer-charge ────────────│
│       ▼                                                         │
│  5. score answer   objective checks, else LLM judge (free)     │
│       │                                                         │
│       ▼                                                         │
│  6. record(quality, cost, tokens)  ──► SQLite policy store     │
│                                        ▲ price-shift detector  │
│                                        │ re-explores on a move │
└───────────────────────────────────────────────────────────────┘
         │
         ▼
  answer + `arbiter` metadata (task, model, mode, quality, cost, saved)
```

The expensive work (trying models, judging quality) is concentrated in an
**exploration** phase and amortized; steady-state traffic **exploits** what was
learned and is cheap and deterministic.

## The strategies

Each stage a request passes through, and the one-line reason it exists. Full
reasoning - including the alternatives rejected - is in
[docs/strategies.md](docs/strategies.md).

| # | Stage | What it does | Why |
|---|-------|--------------|-----|
| 1 | **Classification** | Label the task (`code`/`math`/`structured`/`factual`/`open`) with rules first, a free model only on ambiguity | Routing is learned per task type; keep it cheap and consistent |
| 2 | **Context filter** | Drop any model whose window can't hold the prompt, before routing | Capacity is a fact, not a preference - correctness before cost |
| 3 | **Budget filter** | Drop any model over a caller's `arbiter_max_cost` ceiling | Let the caller pick a cost tier even though the operator pays |
| 4 | **Routing policy** | Explore each candidate a few times, then exploit the cheapest model within a quality tolerance of the best | Self-calibrating and trivially explainable; pays up only when it must |
| 5 | **Objective scoring** | Grade code (parses), math (evaluates), structured (valid JSON) for free | A trustworthy 0..1 quality signal at zero cost |
| 6 | **LLM judge** | For open/factual answers, a free model rates quality - but only while exploring | Subjective quality without adding a call to the hot path |
| 7 | **Measured savings** | Re-price every call against the baseline's *measured* mean cost, from headers | Credible savings - real numbers on both sides, never list prices |
| 8 | **Price-shift re-exploration** | Watch each model's unit price; a large move wipes its stats and re-routes | Turns a static router into **live arbitrage** - the signature feature |

Plus a **quarantine** guard: a model that errors is skipped for a few minutes so
a broken provider can't stall routing, and recovers automatically.

## What's on the dashboard

A single service serves both the API and a Next.js UI:

- **Overview** - calls routed, spend, avg cost/call, task types learned, a live
  routing feed, and price-shift alerts.
- **Playground** - send a real prompt and watch it get classified, routed,
  scored and priced live; a budget slider previews the whole market.
- **API key** - mint a key, see usage against rate limits, pause/resume/revoke.
- **Models** - the routable pool and the full runtime catalog.

## Layout

```
arbiter/      FastAPI app: routing, scoring, policy store, BTL client
  main.py       OpenAI-compatible endpoint + dashboard API
  policy.py     the bandit routing brain (SQLite-backed)
  classifier.py hybrid task classification
  scoring.py    objective quality checks
  judge.py      LLM-as-judge for subjective tasks
  models.py     the routable model pool
ui/           Next.js dashboard + Fumadocs, exported static and served by FastAPI
docs/         the reasoning: architecture, strategies, API, roadmap
scripts/      dev server + a load/seed bench
```

## Docs

- [architecture.md](docs/architecture.md) - components and data flow
- [strategies.md](docs/strategies.md) - every routing decision and why
- [api-reference.md](docs/api-reference.md) / [developers.md](docs/developers.md) - the HTTP surface
- [roadmap.md](docs/roadmap.md) - what's shipped and what's next
