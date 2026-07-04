# Roadmap

This is an honest plan, not a wish list. It starts from the limitations the
current build already acknowledges (see [strategies.md](strategies.md) and
[integration.md](integration.md)) and orders work by impact, not by how
interesting it is to build.

**Guiding principle: trust before reach.** Make Arbiter safe and reliable to run
for real (Phase 1), then make its routing genuinely smarter (Phase 2), then
expand what it can reach (Phase 3). A clever router nobody can safely deploy is
worth less than a simple one they can.

Effort is tagged **S** (days), **M** (a week or two), **L** (larger).

---

## Phase 1 — Harden: make it safe to run for real

These are the things that block using Arbiter outside a trusted network. They
are not glamorous; they are the difference between a demo and a service.

- **Client authentication & multi-tenancy** *(M)* — the top blocker. Today the
  proxy is open: anyone who reaches it spends the operator's BTL key, and
  everyone shares one policy. Add per-client keys, and optionally per-tenant
  policies so teams don't pollute each other's learning.
- **Budget guardrails** *(S)* — per-key and global spend caps, with a hard stop
  and alerting. A cost router should be the *last* thing to run up a surprise
  bill.
- **Reliability & failover** *(M)* — on a provider/runtime error or timeout,
  retry and fall back to the next-best eligible model instead of failing the
  request. Turns the router into a resilience layer, not a single point of
  failure.
- **Streaming responses** *(M)* — support Server-Sent Events pass-through.
  Interactive apps expect token streaming; today Arbiter only returns whole
  responses. Scoring on a streamed answer needs care (grade on completion).
- **Durable metrics** *(S)* — the decision feed, alerts, and counters are
  in-memory and vanish on restart. Persist them and expose a time series so
  savings history survives and can be exported.
- **Horizontal scale** *(L)* — the policy is a single-file SQLite store behind a
  global lock, fine for one process. Move it to a shared store (Postgres/Redis)
  so multiple Arbiter instances share one brain and scale out.

## Phase 2 — Deepen: route smarter

These attack the quality of the routing decision itself — the places where the
current heuristics are honest but shallow.

- **Warm-start from public benchmarks** *(M)* — seed each model's quality prior
  from published results (HumanEval→code, GSM8K→math, etc.), decaying the prior
  as live data arrives. Kills the cold-start "tuition" phase where savings sit
  near zero.
- **Stronger quality signals** *(L)* — the biggest lever. Today code is only
  *parsed*, not run, and open-ended quality leans on a single judge. Add:
  sandboxed code execution against tests, reference/embedding-based grading, and
  a human feedback loop (👍/👎 from the calling app) that overrides model
  judgement.
- **Per-prompt difficulty routing** *(M)* — route by how hard *this* request is,
  not just its coarse task type. Two math prompts of very different difficulty
  currently get the same treatment. Pair with an **in-request confidence
  cascade**: try cheap, escalate within the same request only when the answer
  looks weak.
- **Semantic caching** *(M)* — dedupe near-identical prompts (not just exact
  matches) and serve a cached answer for free. Complements the runtime's own
  exact-cache with embedding-based similarity.
- **Statistical drift & price detection** *(S)* — replace the fixed
  `PRICE_SHIFT` / quality thresholds with proper change-point detection, so the
  router reacts to real shifts sooner and false-alarms less.
- **Latency-aware routing** *(M)* — make routing multi-objective: cost, quality,
  *and* speed. Let a caller ask for "cheapest under 800ms" for interactive
  paths.

## Phase 3 — Expand: reach more

Once it's trustworthy and smart, widen what it can do.

- **Anthropic `/v1/messages` surface** *(M)* — the current pool is
  OpenAI-surface only, so every Claude model is excluded. Add the second
  protocol surface and translate, unlocking a large set of strong models as
  routing candidates.
- **Self-updating registry** *(S)* — auto-discover models, context windows, and
  prices from the runtime's `GET /v1/models` instead of a hand-maintained list,
  so new models enter the pool automatically.
- **Shadow / challenger routing** *(M)* — send a small traffic slice to new or
  candidate models to keep quality/price estimates fresh and safely A/B new
  entrants before promoting them.
- **Multi-modal routing** *(L)* — extend classification, scoring, and routing to
  vision and audio requests, not just text.
- **Explainability & analytics** *(S)* — a cost/quality Pareto view per task,
  and a per-decision "why this model" trace, so operators can audit and trust
  the routing.

---

## Concerns → where they're addressed

A map from today's known limitations to the item that fixes them.

| Known limitation (today) | Addressed by |
|--------------------------|--------------|
| Open proxy; caller key ignored | Phase 1 · Client auth & multi-tenancy |
| No spend ceiling | Phase 1 · Budget guardrails |
| Single point of failure on provider errors | Phase 1 · Reliability & failover |
| No streaming | Phase 1 · Streaming responses |
| Feeds/metrics lost on restart | Phase 1 · Durable metrics |
| SQLite + global lock won't scale out | Phase 1 · Horizontal scale |
| Cold-start tuition (savings ≈ 0% early) | Phase 2 · Warm-start priors |
| "Parses" ≠ "correct"; judge is imperfect | Phase 2 · Stronger quality signals |
| Coarse task buckets; classifier can misfire | Phase 2 · Per-prompt difficulty routing |
| Only exact cache (via runtime), none of our own | Phase 2 · Semantic caching |
| Heuristic price/quality thresholds | Phase 2 · Statistical drift detection |
| Claude / Anthropic models unreachable | Phase 3 · `/v1/messages` surface |
| Hand-maintained model registry | Phase 3 · Self-updating registry |

## Non-goals (for now)

To keep focus, Arbiter deliberately does **not** aim to:

- Train or fine-tune its own models — it routes, it doesn't build models.
- Be a general-purpose API gateway (rate limiting, transformations, etc.) — it
  stays a *routing* layer.
- Replace the runtime — Arbiter is built *on* BTL and depends on its cost
  telemetry; it is not a provider abstraction that hides it.
