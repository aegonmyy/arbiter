# Deploying Arbiter

Two pieces: the **backend** (the FastAPI router — required) and the **UI** (the
Next.js dashboard — optional, since the backend already serves a dashboard at
`/`).

## Backend → Railway

The repo ships `Procfile`, `.python-version`, and `railway.toml`, so Railway
needs almost no setup.

1. **New Project → Deploy from GitHub → `aegonmyy/arbiter`** (root directory =
   repo root; Nixpacks detects Python from `requirements.txt`).
2. **Variables:**
   | Variable | Value |
   |----------|-------|
   | `GATEWAY_API_KEY` | your BTL key (`gw_…`) — mark as secret |
   | `BASELINE_MODEL` | `gpt-4o` |
   | `ARBITER_DB` | `/app/data/arbiter.db` |
3. **Volume:** add one, mount path **`/app/data`**. Without it, the learned
   routing policy resets on every redeploy (it's a SQLite file).
4. Deploy. Railway injects `$PORT`; the app binds to it and passes the
   `/health` check. Add a custom domain (e.g. `arbiter-api.ameenme.dev`).

That single URL serves the API **and** the built-in dashboard at `/`.

> The same `Procfile` works on Render, Fly.io, or Heroku — only the volume and
> variable UI differ.

## UI → Vercel (optional)

1. **New Project → import `aegonmyy/arbiter`**, set **Root Directory = `ui`**.
   Vercel auto-detects Next.js.
2. **Variable:** `ARBITER_BACKEND` = the backend's public URL
   (e.g. `https://arbiter-api.ameenme.dev`). The Next rewrite proxies `/v1/*`
   there server-side, so the browser makes same-origin calls (no CORS).
3. Deploy. Add a domain (e.g. `arbiter.ameenme.dev`).

## Environment variables at a glance

**Backend**

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `GATEWAY_API_KEY` | yes | — | BTL runtime key; authenticates every runtime call. |
| `BASELINE_MODEL` | no | `gpt-4o` | Premium model savings are measured against. |
| `ARBITER_DB` | no | `data/arbiter.db` | SQLite path; point at a volume in production. |
| `BTL_BASE_URL` | no | `https://api.badtheorylabs.com/v1` | Runtime base URL. |
| `BASELINE_CONTEXT` | no | `128000` | Baseline context window. |
| `REQUEST_TIMEOUT` | no | `120` | Per-request timeout (seconds). |
| `PORT` | injected | — | Provided by the host. |

**UI**

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `ARBITER_BACKEND` | yes (prod) | `http://localhost:8000` | Backend URL the `/v1` rewrite proxies to. |

## Security note

The proxy has no client authentication yet — anyone who can reach the backend
URL spends your BTL key. Until client-auth is added (see
[docs/roadmap.md](docs/roadmap.md)), keep the URL private and/or set a spend cap
on your BTL account.
