# Arbiter

A drop-in, OpenAI-compatible router that sends each request to the best
model-for-the-money instead of paying premium prices for every call.

You point your existing OpenAI client at Arbiter, keep your code exactly as it
is, and Arbiter forwards the request to the Bad Theory Labs runtime - picking a
model per request based on what actually works for that kind of task and what it
costs. It reads the runtime's cost headers on every response, so the savings are
measured, not guessed.

## Why it exists

Most teams hardcode one expensive model for everything. A lot of that traffic is
simple enough for a model that costs 10-30x less, but nobody has a principled way
to route it, and no visibility into what they're actually spending per call.

Arbiter closes both gaps:

- **Route** each request to the cheapest model that still gets it right.
- **Prove** the savings from the runtime's own `x-btl-*` billing headers.

## How it works

1. Your client calls Arbiter's `/v1/chat/completions` (OpenAI-compatible).
2. Arbiter classifies the request into a task type.
3. A routing policy picks a model. New task types are explored across a few
   candidates; once a clear winner emerges, traffic exploits it.
4. The request goes to the BTL runtime with the chosen model.
5. Arbiter scores the answer, reads the cost headers, and updates the policy.

## Running it

```bash
cp .env.example .env      # add your GATEWAY_API_KEY
./scripts/dev.sh          # starts the proxy on :8000
```

Then point any OpenAI client at `http://localhost:8000/v1`.
