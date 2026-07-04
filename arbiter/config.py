import os
from pathlib import Path


def _load_env_file(path: Path) -> None:
    """Minimal .env loader so we don't drag in a dependency for four lines."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_env_file(Path(__file__).resolve().parent.parent / ".env")

BTL_BASE_URL = os.environ.get("BTL_BASE_URL", "https://api.badtheorylabs.com/v1")
GATEWAY_API_KEY = os.environ.get("GATEWAY_API_KEY", "")

# The model we pretend a naive team would use for everything. Savings are
# reported relative to this.
# The premium model savings are measured against. Must be an OpenAI-surface
# route (the /v1/chat/completions models); Anthropic-direct models won't work.
BASELINE_MODEL = os.environ.get("BASELINE_MODEL", "gpt-4o")

# Assumed context window for the baseline when it isn't one of the registry
# candidates. gpt-4o is 128k; override if you point BASELINE_MODEL elsewhere.
BASELINE_CONTEXT = int(os.environ.get("BASELINE_CONTEXT", "128000"))

REQUEST_TIMEOUT = float(os.environ.get("REQUEST_TIMEOUT", "120"))

# Client API keys that callers must present. Comma-separated. When empty, client
# auth is disabled and the proxy is open (the current default).
ARBITER_API_KEYS = frozenset(
    k.strip() for k in os.environ.get("ARBITER_API_KEYS", "").split(",") if k.strip()
)


def require_key() -> str:
    if not GATEWAY_API_KEY:
        raise RuntimeError(
            "GATEWAY_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    return GATEWAY_API_KEY
