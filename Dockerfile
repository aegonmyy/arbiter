# One image that builds the Next.js UI to a static export and serves it - plus
# the API - from a single FastAPI process. One repo, one service, one URL.

# ---- Stage 1: build the UI to a static export ----
FROM node:20-slim AS ui
WORKDIR /ui
COPY ui/package.json ui/package-lock.json ./
RUN npm ci
COPY ui/ ./
RUN NEXT_OUTPUT=export npm run build

# ---- Stage 2: Python runtime that serves the API + the exported UI ----
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY arbiter/ ./arbiter/
COPY --from=ui /ui/out ./ui/out

ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn arbiter.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
