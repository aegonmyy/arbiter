# Arbiter UI

The dashboard for Arbiter - a Next.js app on the same StreamWage design system
(indigo/teal, Geist, large radius), with a proper light/dark toggle and live
charts.

It is the richer alternative to the single-file dashboard the proxy serves at
`/`. Run it alongside the proxy.

## Run

```bash
# 1. start the Arbiter proxy (in the repo root)
./scripts/dev.sh                 # serves the API on :8000

# 2. start the UI
cd ui
npm install
npm run dev                      # http://localhost:3000
```

The UI proxies `/v1/*` to the Arbiter backend via a Next rewrite, so the browser
makes same-origin calls (no CORS). Point it at a different backend with
`ARBITER_BACKEND`:

```bash
ARBITER_BACKEND=http://my-host:8000 npm run dev
```

## Layout

- `app/` - layout, global tokens, and the page.
- `components/` - Header, Hero (with the integration snippet), StatsBar,
  MiniStats, SavingsChart (recharts), RoutingFeed, PolicyTable, RightRail.
- `lib/api.ts` - typed SWR hooks over the Arbiter endpoints.
