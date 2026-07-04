# Deploying Arbiter

**One repo, one service, one URL.** A single Docker image builds the Next.js UI
to a static export and serves it *and* the API from one FastAPI process. The
dashboard (`/`), the docs (`/docs`), and the API (`/v1`) all live on the same
origin - so there's no second deploy, no CORS, and no cross-service wiring.

## Deploy to Railway

The repo ships a `Dockerfile` and `railway.toml`, so Railway builds and runs it
with almost no setup.

1. **New Project -> Deploy from GitHub -> `aegonmyy/arbiter`.** Railway sees the
   `Dockerfile` and uses it (builds the UI, then the Python runtime).
2. **Variables** (service -> Variables):
   | Variable | Value |
   |----------|-------|
   | `GATEWAY_API_KEY` | your BTL key (`gw_...`) - secret |
   | `BASELINE_MODEL` | `gpt-4o` |
   | `ARBITER_DB` | `/app/data/arbiter.db` |
3. **Volume:** service -> `⌘K`/`Ctrl+K` -> *Create Volume* -> mount path
   **`/app/data`**. Without it the learned routing policy (a SQLite file) resets
   on every redeploy.
4. **Expose a public URL** - this is the step that's easy to miss. A Railway
   service is private by default. Open **Settings -> Networking -> Generate
   Domain**. Railway detects the port (the app binds `$PORT`) and gives you a
   `*.up.railway.app` URL. Add a custom domain there too if you like
   (e.g. `arbiter.ameenme.dev`).
5. Visit the URL: `/` is the landing page, `/app` the dashboard, `/docs` the
   documentation, `/v1/...` the API.

That's the whole deploy. The same `Dockerfile` runs on Render, Fly.io, or any
container host.

## Environment variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `GATEWAY_API_KEY` | yes | - | BTL runtime key; authenticates every runtime call. |
| `BASELINE_MODEL` | no | `gpt-4o` | Premium model savings are measured against. |
| `ARBITER_DB` | no | `data/arbiter.db` | SQLite path; point at the volume in production. |
| `BTL_BASE_URL` | no | `https://api.badtheorylabs.com/v1` | Runtime base URL. |
| `BASELINE_CONTEXT` | no | `128000` | Baseline context window. |
| `REQUEST_TIMEOUT` | no | `120` | Per-request timeout (seconds). |
| `PORT` | injected | `8000` | Provided by the host. |

## Local development

Two ways to run it locally:

- **Fast UI iteration** (hot reload, two processes):
  ```bash
  ./scripts/dev.sh              # backend on :8000
  cd ui && npm run dev          # UI on :3000, proxies /v1 to :8000
  ```
- **Production-like** (one process, mirrors the deploy):
  ```bash
  cd ui && npm run build:export # writes ui/out
  cd .. && ./scripts/dev.sh     # FastAPI now serves ui/out at / and /docs
  ```

`ARBITER_BACKEND` only matters for the two-process dev mode (it tells the Next
dev server where to proxy `/v1`); it isn't used in the single-service deploy.

## Security note

The proxy has no client authentication yet - anyone who can reach the URL spends
your BTL key. Until client-auth is added (see
[docs/roadmap.md](docs/roadmap.md)), keep the URL private and/or set a spend cap
on your BTL account.
