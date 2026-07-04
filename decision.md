# Decision log

Running log of judgment calls made while building the overnight feature batch
(README polish, failover, warm-start priors, latency routing, durable metrics,
drift detection, difficulty routing, semantic caching, feedback loop). Anything
that genuinely needs the operator's input is flagged **NEEDS YOU**.

Newest entries at the top.

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
