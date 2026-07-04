# Arbiter documentation

Arbiter is a drop-in, OpenAI-compatible router. It sits in front of the Bad
Theory Labs (BTL) runtime and sends each request to the cheapest model that
still does the job well - measuring the savings from the runtime's own cost
headers rather than estimating them.

This folder explains what it does, why it works the way it does, and how to run
and integrate it.

## Where to start

- **New here?** Read [architecture.md](architecture.md) for the whole system in
  one pass, then [strategies.md](strategies.md) for the reasoning behind each
  decision.
- **Integrating an app?** Go straight to [integration.md](integration.md).
- **Calling the API in code?** See the [developers.md](developers.md) guide.
- **Wiring against the HTTP API?** See [api-reference.md](api-reference.md).
- **Looking at the web app?** See [interface.md](interface.md).
- **Tuning behaviour?** See [configuration.md](configuration.md).
- **Deploying?** The repo's `DEPLOY.md` covers the single-service Docker deploy
  (one image serves the API, the dashboard, and the docs on one URL).

## The documents

| Document | What it covers |
|----------|----------------|
| [architecture.md](architecture.md) | The request lifecycle and how the pieces fit: Classify -> Filter -> Route -> Grade -> Learn -> React. |
| [interface.md](interface.md) | The web app: the landing page, the onboarding flow, the dashboard tabs, and the Playground. |
| [strategies.md](strategies.md) | Each strategy in depth - classification, the context filter, the routing policy, quality scoring, the judge, and price-shift re-exploration - with the trade-offs behind them. |
| [developers.md](developers.md) | How to call the API: point your OpenAI client at Arbiter, set a budget, stream, manage your key, handle errors - with copy-paste examples. |
| [api-reference.md](api-reference.md) | Every HTTP endpoint, request and response shapes, and the `arbiter` block added to each completion. |
| [integration.md](integration.md) | Running Arbiter, pointing an OpenAI client at it, and the key / auth model. |
| [configuration.md](configuration.md) | Environment variables, the model registry, and the tunable thresholds. |
| [roadmap.md](roadmap.md) | What's next: hardening, smarter routing, and wider reach - and which limitation each item addresses. |

## Conventions used in these docs

- **Baseline** means the premium model we measure savings against (`gpt-4o` by
  default). "Savings" always means *versus running everything on the baseline*.
- **Task type** is one of `code`, `math`, `structured`, `factual`, `open`.
- **Explore / exploit** describe the two routing modes: gathering data about a
  model versus using what has already been learned.
- Model ids (e.g. `deepseek-chat-v3`) refer to routes on the BTL runtime that
  answer on the `/v1/chat/completions` surface.
- Code references are given as `file:function`, e.g. `policy.py:choose`.

## The one-paragraph version

A request arrives dressed as an OpenAI call. Arbiter classifies it, drops any
model whose context window can't hold it, and routes it to the cheapest
remaining model whose learned quality is within tolerance of the best. It sends
that to the runtime, grades the answer, and folds the measured cost and quality
back into a shared, persistent policy - so the next similar request is routed
better. If a model's price moves, Arbiter notices and re-routes. The savings are
read from the runtime's `x-btl-*` headers, so they are measured, not guessed.
