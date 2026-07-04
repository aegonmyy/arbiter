# Decision log

Running log of judgment calls made while building the overnight feature batch
(README polish, failover, warm-start priors, latency routing, durable metrics,
drift detection, difficulty routing, semantic caching, feedback loop). Anything
that genuinely needs the operator's input is flagged **NEEDS YOU**.

Newest entries at the top.

---

## Stronger quality signals: shipped the feedback loop, deferred the rest (NEEDS YOU)

"Stronger quality signals" (roadmap Phase 2, tagged L) had three parts. I built
the one that is safe and self-contained and **deferred two that genuinely need
your call**:

- ✅ **Human 👍/👎 feedback loop** — shipped. `POST /v1/feedback` folds votes into
  routing quality with high weight (overrides the judge). Safe, no new deps.
- ⛔ **Sandboxed code execution** (run model-written code against tests instead of
  only parsing it). **Needs a decision from you:** running untrusted model output
  requires a real sandbox (container / gVisor / firecracker / a service like
  Piston or Judge0), which is infra and a security surface I shouldn't stand up
  unattended. Options when you're back: (a) a hardened subprocess with seccomp +
  resource limits, (b) an external code-execution service, (c) leave code at
  "parses" and lean on the feedback loop. My lean: (b) for real use, (c) for the
  hackathon — the feedback loop already strengthens the signal.
- ⛔ **Embedding-based grading / semantic cache** — deferred. Needs an embeddings
  model. BTL may expose one, but I didn't want to hard-code an endpoint I haven't
  verified. The cache I shipped is lexical (token-set Jaccard); swapping in
  embeddings is a clean upgrade once we confirm an embeddings route on the runtime.

Neither blocks anything shipped tonight; both are noted in the roadmap.

---

## Difficulty routing: only hard prompts get a sub-bucket (backward-compatible)

**Decision.** Per-prompt difficulty routing splits each task into `easy`/`hard`,
but **only hard prompts get a new policy key** (`code:hard`); easy prompts keep
using the base task bucket (`code`).

**Why.** Making the key always `task:difficulty` would strand all the learning
the live instance already has under `code`/`math`/... and double the exploration
(and baseline sampling) cost. Sub-bucketing only the hard tail preserves the
common-case learning and adds granularity exactly where task type is too coarse.
Side effect: the policy snapshot / "task types learned" count now shows entries
like `code:hard`. That's intentional and demoable, not a bug.

**Confidence cascade caveat (minor).** When the cascade escalates and the
stronger answer turns out *not* to be better, we keep the original answer but
have already paid for the probe call; that probe's cost isn't attributed to the
request. It's zero for free models and negligible otherwise. Flagging in case you
want strict spend accounting later.

---

## Deployment: holding the live deploy until you review (NEEDS YOU: just a yes)

**Decision.** I am landing every change as local git commits with a green test
suite, but **not pushing to `origin`/redeploying Railway overnight.**

**Why.** The live instance at `arbiter-production-a19e.up.railway.app` is
currently in a known-good, fully-seeded demo state (991 calls, $0 spent,
populated dashboard). A push auto-redeploys via the Dockerfile. Shipping a large
batch of changes unattended, right before the deadline, risks breaking the one
thing that's demonstrably working while you're asleep and can't smoke-test it.
The seeded data lives in the mounted volume (`ARBITER_DB`) and survives a
redeploy, so there is no urgency to deploy tonight.

**What you do in the morning:** review the diff, then either `git push` (Railway
redeploys in a few minutes) or tell me to. I'll smoke-test `/health` + a live
routing call right after.

---

## Seed result (context)

Seed finished before this batch started: **991 calls, $0 actual spend**,
classifier split 792 rules / 208 model, 0 alerts. Everything routed to
`deepseek-v4-flash` (free). Dashboard is populated and demo-ready.
