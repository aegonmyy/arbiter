"""Thin client for the Bad Theory Labs runtime.

Everything Arbiter sends to a model goes through here. Besides the response
body, we care about the cost headers the runtime attaches to every reply - they
are how we measure savings instead of estimating them.
"""
from dataclasses import dataclass
from typing import Any

import httpx

from . import config


@dataclass
class Cost:
    """What a single call actually cost, pulled from the runtime headers.

    `charged` is the number that matters to us: the real dollar cost of this
    call. Routing savings are the difference between the baseline model's
    charge and the routed model's charge, so we always have a measured figure
    rather than an estimate.
    """

    charged: float | None = None      # x-btl-customer-charge
    saved: float | None = None        # x-btl-saved (runtime-side, e.g. cache)
    benchmark: float | None = None    # x-btl-benchmark-cost
    cache_tier: str | None = None     # x-btl-cache-tier (only on cache hits)

    @classmethod
    def from_headers(cls, headers: httpx.Headers) -> "Cost":
        def num(name: str) -> float | None:
            raw = headers.get(name)
            if raw is None:
                return None
            try:
                return float(raw)
            except ValueError:
                return None

        return cls(
            charged=num("x-btl-customer-charge"),
            saved=num("x-btl-saved"),
            benchmark=num("x-btl-benchmark-cost"),
            cache_tier=headers.get("x-btl-cache-tier"),
        )


@dataclass
class Completion:
    body: dict[str, Any]
    cost: Cost
    model: str

    @property
    def text(self) -> str:
        try:
            return self.body["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            return ""


class BTLClient:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=config.BTL_BASE_URL,
            timeout=config.REQUEST_TIMEOUT,
            headers={"Authorization": f"Bearer {config.require_key()}"},
        )

    async def chat(self, payload: dict[str, Any]) -> Completion:
        """Run one chat completion. `payload` is a standard OpenAI request body."""
        resp = await self._client.post("/chat/completions", json=payload)
        resp.raise_for_status()
        body = resp.json()
        return Completion(
            body=body,
            cost=Cost.from_headers(resp.headers),
            model=payload.get("model", ""),
        )

    async def aclose(self) -> None:
        await self._client.aclose()
