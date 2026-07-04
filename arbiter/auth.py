"""Client authentication for the proxy.

Callers present their own Arbiter API key as a Bearer token. This is separate
from the BTL key: the BTL key is the operator's, held server-side; an Arbiter
key is what a client uses to be allowed through.

Auth is opt-in. If no client keys are configured (`ARBITER_API_KEYS` empty), the
check is a no-op and the proxy stays open. Once keys are set, protected
endpoints require a valid one.
"""
from fastapi import Header, HTTPException

from . import config


def auth_enabled() -> bool:
    return bool(config.ARBITER_API_KEYS)


def require_client(authorization: str | None = Header(default=None)) -> None:
    if not config.ARBITER_API_KEYS:
        return  # open proxy: no client keys configured
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if token not in config.ARBITER_API_KEYS:
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid Arbiter API key. Pass 'Authorization: Bearer <key>'.",
        )
