# Developer guide

How to actually call Arbiter. It speaks the OpenAI chat-completions protocol, so
you keep your OpenAI client and change two things: the base URL, and your key.
This guide shows the common tasks with copy-paste examples. For the full endpoint
list see [api-reference.md](api-reference.md).

## 1. Get a key

Every request needs an Arbiter API key. Mint one from an email:

```bash
curl -X POST https://YOUR_HOST/v1/register \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com"}'
# -> { "api_key": "arb_..." }
```

(Or click through the app's `/start` flow, which shows the key.)

## 2. Point your client at Arbiter

The Arbiter key goes where your OpenAI key used to. The SDK sends it as
`Authorization: Bearer <key>`, which is exactly what Arbiter checks.

**Python (OpenAI SDK)**

```python
from openai import OpenAI

client = OpenAI(base_url="https://YOUR_HOST/v1", api_key="arb_...")

r = client.chat.completions.create(
    model="auto",                       # ignored; Arbiter picks the model
    messages=[{"role": "user", "content": "Calculate 88 * 12"}],
)
print(r.choices[0].message.content)
```

**Node (openai)**

```js
import OpenAI from "openai";
const client = new OpenAI({ baseURL: "https://YOUR_HOST/v1", apiKey: "arb_..." });
const r = await client.chat.completions.create({
  model: "auto",
  messages: [{ role: "user", content: "Calculate 88 * 12" }],
});
```

**curl**

```bash
curl https://YOUR_HOST/v1/chat/completions \
  -H "Authorization: Bearer arb_..." -H "Content-Type: application/json" \
  -d '{"model":"auto","messages":[{"role":"user","content":"hi"}]}'
```

## 3. Set a budget (max cost per request)

Cap what a request may cost with `arbiter_max_cost` (USD). Arbiter routes only
among models whose estimated cost for that request is within the ceiling.

Because it is a non-standard field, the OpenAI SDK sends it through
**`extra_body`**:

```python
r = client.chat.completions.create(
    model="auto",
    messages=[{"role": "user", "content": "Summarize this in one line: ..."}],
    max_tokens=200,
    extra_body={"arbiter_max_cost": 0.0005},   # <- the budget ceiling
)
```

Node:

```js
const r = await client.chat.completions.create({
  model: "auto",
  messages: [...],
  max_tokens: 200,
  // @ts-expect-error non-standard field
  arbiter_max_cost: 0.0005,
});
```

curl (it's just a top-level field in the body):

```bash
curl https://YOUR_HOST/v1/chat/completions \
  -H "Authorization: Bearer arb_..." -H "Content-Type: application/json" \
  -d '{"model":"auto","max_tokens":200,"arbiter_max_cost":0.0005,
       "messages":[{"role":"user","content":"..."}]}'
```

## 4. Stream the response

Standard OpenAI streaming - set `stream: true`:

```python
stream = client.chat.completions.create(
    model="auto",
    messages=[{"role": "user", "content": "Write a short poem about the sea."}],
    stream=True,
)
for chunk in stream:
    print(chunk.choices[0].delta.content or "", end="", flush=True)
```

Routing happens before the first token. After the stream, Arbiter emits one extra
`event: arbiter` with the final model, quality, cost and savings (strict clients
ignore it). Read the serving model from that event: on streaming responses it is
not a header, because in-request failover can switch models after the headers are
sent.

## 5. Read what Arbiter decided

Non-streaming responses include an `arbiter` object next to the usual fields:

```python
r = client.chat.completions.create(model="auto", messages=[...])
info = r.model_dump()["arbiter"]
# info["model"], info["task"], info["cost"], info["saved"],
# info["budget_met"], info["eligible_models"], ...
```

See [api-reference.md](api-reference.md#post-v1chatcompletions) for every field.

## 6. Manage your key

All authenticated with the key itself:

```bash
curl https://YOUR_HOST/v1/key -H "Authorization: Bearer arb_..."          # usage + status
curl -X POST https://YOUR_HOST/v1/key/pause  -H "Authorization: Bearer arb_..."
curl -X POST https://YOUR_HOST/v1/key/resume -H "Authorization: Bearer arb_..."
curl -X POST https://YOUR_HOST/v1/key/revoke -H "Authorization: Bearer arb_..."
```

## 7. Errors to handle

| Status | Meaning | What to do |
|--------|---------|------------|
| `401` | Missing or invalid key | Register or fix the `Authorization` header. |
| `403` | Key is paused | Resume it (`/v1/key/resume`). |
| `429` | Rate limit hit (50 / 6h or 600 / week) | Back off; a `Retry-After` header says how long. |
| `4xx` from upstream | The runtime/provider rejected the call | Surfaced with the upstream status; the failed call is not billed to your learning. |

## Notes

- The `model` you send is always ignored - choosing the model is the whole point.
- Everything here is the public API; the web Playground uses exactly these calls.
- Read-only endpoints (`/v1/report`, `/v1/overview`, ...) need no key.
