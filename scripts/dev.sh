#!/usr/bin/env bash
# Start the Arbiter proxy for local development.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d .venv ]; then
    uv venv .venv
    uv pip install --python .venv/bin/python -r requirements.txt
fi

exec .venv/bin/uvicorn arbiter.main:app --reload --port "${PORT:-8000}"
