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

Once it's up, open `http://localhost:8000` for the dashboard, or
`http://localhost:8000/health` to confirm it's live.

## Pointing an app at it (client)

Integration is a one-line change: swap the base URL of your existing OpenAI
client. Keep everything else - the same SDK, the same request shape.

**Python (OpenAI SDK)**

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="ignored")

r = client.chat.completions.create(
    model="anything",                       # ignored - Arbiter chooses
    messages=[{"role": "user", "content": "Calculate 88 * 12"}],
)
print(r.choices[0].message.content)
```

**curl**

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"x","messages":[{"role":"user","content":"hi"}]}'
```

The same swap works for anything OpenAI-compatible - LangChain, aider, Continue,
n8n, or your own service. No SDK change, no request-shape change.

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
- **No client auth.** Arbiter does **not** check any `Authorization` header from
  callers. Whatever key a client sends is ignored. Anyone who can reach the proxy
  can use it, and they all share one learning brain.
- **One gateway, many apps.** Multiple applications can point at the same
  Arbiter; they all contribute to and benefit from the same shared, persistent
  policy, which is what makes it get cheaper for everyone over time.

**Known limitation.** Because there is no client auth, the proxy is open: treat
it as trusted-network / local only. Before exposing it publicly you would add a
client-key check (callers present their own Arbiter key) so that reaching the
endpoint doesn't mean spending the operator's BTL key. This is deliberately out
of scope for now and noted as the first hardening step.

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
