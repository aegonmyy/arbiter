# Configuration

Arbiter has three layers of configuration: environment variables (deployment
settings), the model registry (which models it may route to), and a handful of
code-level tunables (how it decides). Environment variables are the only ones
you set without touching code.

## Environment variables

Loaded by `config.py` from `.env` (or the real environment, which takes
precedence). See `.env.example`.

| Variable | Default | Purpose |
|----------|---------|---------|
| `GATEWAY_API_KEY` | - (required) | Your BTL machine key. Every runtime call uses it. Arbiter refuses to start a request without it. |
| `BTL_BASE_URL` | `https://api.badtheorylabs.com/v1` | The runtime's OpenAI-compatible base URL. |
| `BASELINE_MODEL` | `gpt-4o` | The premium model savings are measured against. Must be an OpenAI-surface route (not an Anthropic-direct model). |
| `BASELINE_CONTEXT` | `128000` | Assumed context window for the baseline, used by the context filter. Change it if you point `BASELINE_MODEL` at a model with a different window. |
| `REQUEST_TIMEOUT` | `120` | Per-request timeout to the runtime, in seconds. |
| `ARBITER_DB` | `data/arbiter.db` | Path to the SQLite policy store. Point it at a mounted volume in production so learned state survives redeploys. |
| `ARBITER_API_KEYS` | - (empty) | Comma-separated operator keys that bypass rate limits. When empty, only keys minted at signup are accepted. |
| `EMBEDDINGS_API_URL` | - (empty) | An OpenAI-compatible `/embeddings` URL for the semantic cache. When unset, the cache falls back to lexical matching. |
| `EMBEDDINGS_MODEL` | - (empty) | The embedding model name sent to that URL. |
| `EMBEDDINGS_API_KEY` | - (empty) | Bearer key for the embedding provider. The provider is entirely configuration - no vendor is baked into the source. |
| `EMBEDDINGS_THRESHOLD` | `0.80` | Cosine similarity at or above which two prompts count as the same request. |

## The model registry

The pool of models Arbiter may route to lives in `models.py`:

- `CANDIDATES` - the list of routable models, each a `ModelSpec(id, tier,
  context, in_price, out_price)`.
- `BASELINE` - the premium baseline, built from `BASELINE_MODEL` /
  `BASELINE_CONTEXT`.

```python
ModelSpec("deepseek-chat-v3", "small", 128_000, 0.20, 0.80)
#          id                  tier     context   in     out ($/1M tokens)
```

**To add or remove a model**, edit `CANDIDATES`. Each entry needs:

- an **id** that answers on the `/v1/chat/completions` surface - verify with the
  runtime's `GET /v1/models`, and confirm it isn't an Anthropic-direct route
  (those need `/v1/messages` and are out of scope);
- a **tier** (`small`/`mid`/`large`) - a rough prior that only affects the order
  models are explored in, not the final choice;
- the **context window** in tokens, which the filter uses to decide eligibility;
- the **input/output list prices** (`$/1M tokens`), used by the budget filter.

Keeping the pool modest matters: every new model adds `MIN_SAMPLES` exploration
calls per task type before the policy can trust it. A wide, well-spread set of a
handful of models routes better and cheaper than a huge one.

## Role models

Two models play fixed roles rather than being routed to. Both are constants:

| Constant | File | Default | Role |
|----------|------|---------|------|
| `CLASSIFIER_MODEL` | `classifier.py` | `deepseek-v4-flash` | Reads ambiguous prompts to pick a task type. Chosen because it's `$0` on the runtime and, unlike some free models, isn't a reasoning model (see [strategies.md](strategies.md#1-classification--rules-first-a-free-model-on-doubt)). |
| `JUDGE_MODEL` | `judge.py` | `deepseek-v4-pro` | Rates open-ended answers 0..1, during exploration only. |

## Tunables (the policy thresholds)

These live as constants at the top of `policy.py`. They control how the router
learns and reacts. Defaults are chosen to keep the cold start cheap and price
detection quiet; adjust with the trade-offs in mind.

| Constant | Default | Effect | Raise it to... |
|----------|---------|--------|--------------|
| `MIN_SAMPLES` | `2` | Observations per model before its numbers are trusted. | Trust the data more, at a longer/costlier cold start. |
| `EPSILON` | `0.10` | Steady-state chance of re-exploring instead of exploiting. | React faster to drift, at slightly higher steady-state cost. |
| `QUALITY_TOLERANCE` | `0.05` | How much quality you'll trade for a cheaper model. | Prefer cheaper models more aggressively (accepting more quality risk). |
| `PRICE_SHIFT` | `0.75` | Unit-price move that triggers re-learning a model. | Ignore more price noise; lower it to react to smaller moves (risking false alerts). |
| `MIN_TOKENS_FOR_PRICE` | `40` | Token history required before price detection runs. | Reduce false price alerts on tiny, rounding-noisy calls. |
| `PRIOR_STRENGTH` | `1.5` | Weight of the benchmark warm-start prior, in pseudo-observations. | Trust the prior longer before live data overrides it. |
| `FEEDBACK_WEIGHT` | `3.0` | Weight of each human thumbs up/down vote, in pseudo-observations. | Let fewer votes override the judge. |
| `Z_THRESHOLD` / `REL_FLOOR` / `MIN_PRICE_SAMPLES` | `4.0` / `0.10` / `5` | Variance-aware drift detection: a move must be this many sigma *and* this relative size, after this many priced calls. | Catch smaller shifts (lower them) or false-alarm less (raise them). |

A few more live at the top of `main.py`: `MAX_ATTEMPTS` (`3`, models tried per
request before giving up - the first is the routed choice, the rest are
failover), `CASCADE_MIN` (`0.5`, objective score below which the confidence
cascade escalates), and `QUARANTINE_SECONDS` (`300`, how long a model that
errored is skipped). The semantic-cache thresholds live in `cache.py` /
`config.py`.

For the reasoning behind these mechanisms, see
[strategies.md](strategies.md).

## What is *not* configurable (by design)

- **The caller's `model` field.** Always ignored - choosing the model is the
  product.
- **Per-user / per-session state.** There is one shared, persistent policy; there
  is no isolation to configure.
- **The routing decision itself.** The cheapest-within-tolerance rule is fixed;
  you tune its thresholds, not the rule.

Client keys and per-key rate limits *are* configurable - see
[integration.md](integration.md#client-authentication).
