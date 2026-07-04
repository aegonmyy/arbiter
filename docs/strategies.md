# Strategies

This is the reasoning behind Arbiter. Each section states the problem, the
approach taken, and — where it matters — why the obvious alternative was
rejected. The stages appear in the order a request meets them.

A theme runs through all of them: **spend to learn, then coast on what you
learned.** The expensive work (trying models, judging quality) is concentrated
in an exploration phase and amortized; steady-state traffic is cheap and
deterministic.

---

## 1. Classification — rules first, a free model on doubt

**Problem.** Routing is learned per task type, so every request needs a label
(`code`, `math`, `structured`, `factual`, `open`). This runs on every request,
so it must be cheap; but it also needs to be right often enough that similar
requests land in the same bucket.

**Approach.** A two-tier classifier (`classifier.py:classify_smart`):

1. **Rules first.** Deterministic keyword/pattern matching (`classify.py`)
   handles the clear cases instantly and for free — a code fence, `calculate
   5*5`, "return JSON". No network call.
2. **A free model on ambiguity.** When no rule matches, ask a model that costs
   `$0` on the runtime (`deepseek-v4-flash`) to name the type.
3. **Fallback.** If that call fails or returns something unparseable, treat the
   request as `open`. Classification never blocks a request.

**Why not just always call a model?** Even a free model adds a network
round-trip to every request. The rules resolve the obvious majority with zero
latency; the model is reserved for the genuinely ambiguous minority. It is
itself a small arbitrage: escalate only when it's worth it.

**Why `deepseek-v4-flash` specifically?** It was chosen empirically. Several
free models were tested; some — notably `gpt-oss-20b` — are *reasoning* models
that spend a small token budget "thinking" and return an empty answer. Flash is
a non-reasoning instruct model that emits the type word directly. (The same trap
appears again with the judge; see §5.)

**Honest limitation.** Keyword rules can misfire ("write a poem about
*calculating* the stars" could read as math). The bucket only needs to be
*consistent*, not philosophically perfect, so occasional mislabels mostly cost a
little routing accuracy rather than breaking anything.

---

## 2. Context filter — an eligibility gate before routing

**Problem.** The cheapest good model is the wrong choice if the prompt doesn't
fit its context window. Cost must never override "can this model physically do
the request?"

**Approach.** Each model in the registry carries its context window
(`models.py`). Before routing, the request estimates the tokens it needs
(~4 characters per token, plus the requested `max_tokens`) and keeps only models
that fit (`models.py:fits`). The router then chooses only among that eligible
set. If a prompt is so large that nothing fits, it falls back to the full pool
rather than refusing.

**Why a hard gate, not a learned signal?** Context capacity is a fact, not a
preference — there's nothing to learn. A model that can't hold the prompt will
fail or truncate every time. So this is a deterministic filter that runs *ahead*
of the cost/quality decision, not something the policy discovers by trial.

**Consequence worth noting.** For a very large prompt, even the premium baseline
(`gpt-4o`, 128k) is excluded, and routing happens among the large-context models
only. Correctness first.

---

## 3. Routing policy — explore, then exploit the cheapest good model

**Problem.** For each task type, pick the model that minimizes cost without
sacrificing quality — while having started out knowing nothing about any model.

**Approach** (`policy.py:choose`). A bandit-style explore/exploit loop over the
eligible models (the baseline included as a candidate):

- **Explore.** Any model with fewer than `MIN_SAMPLES` observations for this task
  is tried, least-sampled first, so data spreads evenly. This is the cold-start
  "tuition" phase.
- **Exploit.** Once every model has enough data, apply one rule: **the cheapest
  model whose mean quality is within `QUALITY_TOLERANCE` of the best mean
  quality seen for this task.**
- **Re-check.** With probability `EPSILON` it re-explores anyway, so a model that
  has changed doesn't go unnoticed.

**Why "cheapest within tolerance of the best" and not other objectives?**

- *Cheapest that works (quality above a fixed bar)* needs an absolute quality
  threshold that differs per task — fragile.
- *Best quality per dollar* tends to over-reward ultra-cheap models even when
  they're meaningfully worse.
- *Cheapest within tolerance of the best* is self-calibrating (the bar is "close
  to the best we've actually seen here") and trivially explainable — the exact
  reason is returned in the decision. On hard tasks where only a strong model
  clears the bar, it correctly pays up; on easy tasks a cheap model wins.

**Why include the baseline as a candidate?** Sometimes the premium model really
is the only one good enough. Treating it as just another candidate means the
policy can choose it when warranted, and its measured cost is what savings are
computed against (see §6).

**Honest limitation.** With `MIN_SAMPLES = 2`, early estimates are noisy; a model
can get an unlucky sample. `EPSILON` re-exploration and ongoing traffic correct
this over time, trading a little early accuracy for a cheap cold start.

---

## 4. Quality scoring — objective checks where the truth is knowable

**Problem.** The router can only prefer a cheaper model if it can tell whether
that model actually did the job — and it has to tell *without a human*.

**Approach** (`scoring.py`). Where a task has a checkable answer, check it, for
free and with confidence:

- **code** — extract the code and confirm it parses (a syntax check, not
  execution, so it's safe). Non-code prose scores low.
- **math** — if the prompt is a plain arithmetic expression, evaluate it and
  confirm the answer contains the right number.
- **structured** — confirm the response contains valid JSON.

These produce a trustworthy 0..1 signal at no cost. Open-ended and factual tasks
have no ground truth here and get a neutral score, deferred to the judge (§5).

**Why syntax-check code instead of running it?** Executing arbitrary
model-written code is a security risk and needs a sandbox. Parsing catches the
most common failure (broken, non-runnable output) with zero execution risk. It's
a deliberate correctness-vs-safety trade.

**Honest limitation.** "Parses" is weaker than "is correct" — code can parse and
still be wrong. The objective checks are proxies, strong enough to separate good
models from bad ones in aggregate, not to certify any single answer.

---

## 5. The judge — subjective quality, kept cheap by exploring only

**Problem.** Open-ended and factual answers have no objective check, but the
router still needs a quality number for them.

**Approach** (`judge.py`). Ask one capable model (`gpt-4o`) to rate the answer
0..1. The key move is *when*: **the judge runs only while exploring a task
type.** Once a model's quality for a task is known, exploitation reuses that
learned number instead of paying for another judgement
(`main.py:chat_completions` chooses between judging and reusing based on the
decision mode).

**Why gate it to exploration?** The judge is a premium model. Calling it on
every open-ended request would add a premium cost to the very traffic we're
trying to make cheap — self-defeating. Fencing it to exploration makes it a
bounded, one-time cost per model (a few gradings), folded honestly into the
"savings ≈ 0%" tuition phase. By the time savings climb, the judge has gone
quiet.

**Honest limitation.** LLM-as-judge is imperfect and can be biased toward
verbose answers; and a reused learned score can go stale if a model changes.
`EPSILON` re-exploration re-invokes the judge occasionally to refresh it.

---

## 6. Measuring savings — from headers, not list prices

**Problem.** "You saved X%" is only credible if X is measured. Estimated savings
from published per-token prices are easy to inflate and easy to distrust.

**Approach.** Every runtime response carries the real cost of that call in
`x-btl-customer-charge`; Arbiter reads it on every request (`btl.py:Cost`).
Savings are then computed as (`policy.py:report`):

- **Actual spend** — the exact sum of the charges we were billed.
- **Baseline-equivalent spend** — each call re-priced at the *measured* mean cost
  of the baseline (`gpt-4o`) for that task type. The baseline is sampled like any
  other candidate, so this figure is grounded in real charges too.
- **Savings** = baseline-equivalent − actual. Tasks where the baseline hasn't
  been sampled claim no savings.

**Why re-price against a measured baseline mean rather than call the baseline
every time?** Calling the baseline on every request to compare would double the
cost and defeat the purpose. Using its measured mean cost for the task keeps the
comparison honest (real numbers on both sides) without paying twice.

**Why this depends on BTL.** A raw provider key gives you a bill, not a
per-call cost header. This measured-savings story only exists because the runtime
reports cost per response — which is also why the same signal powers §7.

---

## 7. Reacting to price changes — arbitrage, not a one-time decision

**Problem.** A model chosen because it was cheap can stop being cheap. A router
that decides once and never revisits will keep sending traffic to a model that's
no longer the bargain.

**Approach** (`policy.py:record`). Arbiter tracks each model's **unit price**
(cost per token) from the headers. When a new call's unit price moves more than
`PRICE_SHIFT` from the learned average, that model's stats for the task are
wiped: it drops back into exploration, is re-priced at the new rate, and the
router re-routes accordingly. A verified example: an 8× hike on the chosen math
model drops it and moves traffic to the next-cheapest.

**Why unit price (per token), not per-call cost?** Per-call cost varies with
prompt and answer length, so comparing raw call costs would fire on every long
prompt. Cost *per token* isolates an actual rate change from normal size
variation.

**Why a stability guard?** Very small calls have large rounding noise in their
unit price (charges are quantized). The detector ignores a model until it has
accumulated at least `MIN_TOKENS_FOR_PRICE` tokens of history and uses a
deliberately high `PRICE_SHIFT` (0.75), so ordinary noise doesn't trigger false
re-exploration. This was tuned after early thresholds produced spurious alerts.

**Why this is the signature feature.** It turns a static router into live
arbitrage: it consumes the runtime's cost telemetry as a control signal and
reallocates when the market moves. Nothing here is possible without a gateway
that reports cost per call.

---

## Cross-cutting decisions

- **OpenAI surface only.** Arbiter routes on `/v1/chat/completions`, so its
  candidate pool is the runtime's OpenAI-compatible routes. Anthropic-direct
  models (all Claude) answer on `/v1/messages` and are intentionally out of
  scope; adding that surface is future work.
- **Shared, persistent learning.** There is one global policy, on disk, shared
  by all traffic (see [architecture.md](architecture.md#state-and-persistence)).
  Per-session learning was rejected because it would repay the cold-start tuition
  on every new conversation. Global learning makes the knowledge an asset that
  compounds across everyone who uses the router.
- **Ignore the caller's model.** The incoming `model` field is discarded on
  purpose — model selection is the entire product. Callers keep their code
  unchanged; Arbiter decides.
