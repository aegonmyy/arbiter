"""Optional embedding client for the semantic cache.

Turns text into a vector so the cache can match prompts by *meaning* rather than
shared words - catching paraphrases the lexical matcher misses. The provider is
entirely configuration: it calls whatever OpenAI-compatible `/embeddings` URL is
set in the environment, with the configured model and key. If none is configured,
or a call fails, the caller falls back to lexical matching, so embeddings are a
pure enhancement and never a hard dependency.
"""
import math

import httpx

from . import config


def cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity of two equal-length vectors, in [-1, 1]."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = na = nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / math.sqrt(na * nb)


class Embedder:
    """Async client for an OpenAI-compatible embeddings endpoint. Best-effort:
    any failure returns None so the request is never broken by embedding trouble."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            timeout=min(config.REQUEST_TIMEOUT, 15.0),
            headers={"Authorization": f"Bearer {config.EMBEDDINGS_API_KEY}"},
        )
        self._url = config.EMBEDDINGS_API_URL
        self._model = config.EMBEDDINGS_MODEL

    async def embed(self, text: str) -> list[float] | None:
        text = (text or "").strip()
        if not text:
            return None
        try:
            resp = await self._client.post(
                self._url, json={"model": self._model, "input": text})
            resp.raise_for_status()
            return resp.json()["data"][0]["embedding"]
        except (httpx.HTTPError, KeyError, IndexError, ValueError):
            return None

    async def aclose(self) -> None:
        await self._client.aclose()
