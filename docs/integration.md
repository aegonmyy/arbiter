# Integration

There are two roles here, and they need different things:

- The **operator** runs Arbiter once, with a BTL key. They own the shared
  learning and pay the BTL bill.
- A **client application** points its existing OpenAI client at the operator's
  Arbiter and changes nothing else.

This document covers both, and the key/auth model that connects them.

## Running Arbiter (operator)

**Prerequisites**

- Python 3.12+
- [`uv`](https://github.com/astral-sh/uv) (the dev script uses it to manage the
  virtualenv)
- A BTL machine key

**Steps**

```bash
cp .env.example .env        # then add your key
./scripts/dev.sh            # creates the venv, installs deps, serves on :8000
```

`.env` needs at least:

```
GATEWAY_API_KEY=gw_...            # your BTL key
BTL_BASE_URL=https://api.badtheorylabs.com/v1
BASELINE_MODEL=gpt-4o             # what savings are measured against
```

Once it's up, open `http://localhost:8000` for the landing page, `/app` for the
dashboard, or `/health` to confirm it's live. For the full web app (dashboard,
Playground, docs) see [interface.md](interface.md).

To deploy the whole thing (API + web app + docs) as one service, see the repo's
`DEPLOY.md` - a single Docker image builds the web app and serves it alongside
the API on one URL.

## Pointing an app at it (client)

Integration is essentially a one-line change: swap the base URL of your existing
OpenAI client, and use an Arbiter key (mint one at `/start` or `POST /v1/register`)
where your OpenAI key went. Keep everything else - the same SDK, the same request
shape.

**Python (OpenAI SDK)**

```python
from openai import OpenAI

client = OpenAI(base_url="https://arbiter.ameenme.dev/v1", api_key="arb_...")

r = client.chat.completions.create(
    model="anything",                       # ignored - Arbiter chooses
    messages=[{"role": "user", "content": "Calculate 88 * 12"}],
)
print(r.choices[0].message.content)
```

**curl**

```bash
curl https://arbiter.ameenme.dev/v1/chat/completions \
  -H "Authorization: Bearer arb_..." -H "Content-Type: application/json" \
  -d '{"model":"x","messages":[{"role":"user","content":"hi"}]}'
```

The same swap works for anything OpenAI-compatible - LangChain, aider, Continue,
n8n, or your own service. No SDK change, no request-shape change. Optional
per-request controls (`arbiter_max_cost`, `arbiter_max_latency`,
`arbiter_no_cache`) are covered in [developers.md](developers.md#3-routing-controls-budget-latency-cache).

## What a caller gets back

The response is a standard OpenAI completion, so existing code keeps working
untouched. Callers who want visibility can read the extra `arbiter` block on the
response (see [api-reference.md](api-reference.md#post-v1chatcompletions)) for
the chosen model, quality, cost, and savings - or ignore it entirely.

## The key / auth model

This is the part to understand before exposing Arbiter beyond localhost.

- **One key, server-side.** Every call Arbiter makes to the runtime - answering,
  the free-model classifier, and the judge - uses the single `GATEWAY_API_KEY`
  from `.env`. All cost lands on the operator's BTL account.
- **Clients present their own key.** Callers authenticate with an **Arbiter** key
  (separate from the BTL key) as a Bearer token; the paid and control endpoints
  reject anything else with `401`. See [Client authentication](#client-authentication)
  below.
- **One gateway, many apps.** Multiple applications can point at the same
  Arbiter; they all contribute to and benefit from the same shared, persistent
  policy, which is what makes it get cheaper for everyone over time.

## Client authentication

Callers present their own **Arbiter API key** (separate from the operator's BTL
key) as a Bearer token. The paid endpoint (`/v1/chat/completions`) and the
control endpoints (`/v1/reset`, `/v1/simulate-price`) require one; a missing or
invalid key returns `401`. The read-only observability endpoints stay open so
the dashboard keeps working.

A key is valid if it is either:

- **Minted at signup.** A user gives an email at `/start` (or `POST /v1/register`)
  and gets a key back; the web app saves it in the browser and sends it on every
  Playground request. See [interface.md](interface.md).
- **Configured by the operator.** `ARBITER_API_KEYS` is a comma-separated list of
  keys the operator trusts (handy for scripts, ops, or the benchmark):

  ```
  ARBITER_API_KEYS=arb_first_key,arb_second_key
  ```

So reaching the endpoint no longer means spending the operator's BTL key - only
holders of a valid Arbiter key get through.

**Per-key rate limits.** Minted keys are capped at **50 routed requests per 6
hours** and **600 per week** (rolling windows). Exceeding a limit returns `429`
with the limit that was hit and a `Retry-After` header. Operator keys
(`ARBITER_API_KEYS`) are exempt, so scripts and the benchmark are not throttled.

## Testing it under load

`scripts/bench.py` fires a realistic mixed workload so you can watch the router
learn and the savings climb:

```bash
python scripts/bench.py --n 300 --fresh
```

- `--n` sets the number of requests.
- `--fresh` resets learned state first (calls `POST /v1/reset`).

It prints a running savings line and, at the end, the model each task type
converged on. Watch the dashboard at the same time to see it live.
