"""Client authentication for the proxy.

Callers present their own Arbiter API key as a Bearer token. This is separate
from the BTL key: the BTL key is the operator's, held server-side; an Arbiter
key is what a client uses to be allowed through.

A key is valid if it is either configured by the operator (`ARBITER_API_KEYS`)
or minted at signup and stored in the policy database. Protected endpoints
reject anything else with 401. The signup endpoint and the read-only
observability endpoints stay open.
"""
from fastapi import Header, HTTPException, Request

from . import config


def _bearer(authorization: str | None) -> str:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return ""


def require_client(request: Request, authorization: str | None = Header(default=None)) -> None:
    token = _bearer(authorization)
    if token and token in config.ARBITER_API_KEYS:
        return
    if token and request.app.state.policy.is_valid_key(token):
        return
    raise HTTPException(
        status_code=401,
        detail="Missing or invalid Arbiter API key. Get one at /start, then pass 'Authorization: Bearer <key>'.",
    )
