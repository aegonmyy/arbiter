"""A near-duplicate response cache.

The cheapest call is the one you never make. When a prompt is a near-duplicate of
one we've already answered well, we can serve the stored answer for free instead
of routing it to a model at all. This complements the runtime's own exact cache:
that keys on byte-for-byte identical inputs, whereas this tolerates wording
differences.

The cache matches two ways. When an embedding vector is supplied for the prompt
(an embedding provider is configured), it matches by cosine similarity of meaning,
so it catches paraphrases with entirely different words. When no vector is
available, it falls back to a purely local token-set (Jaccard) overlap, which
still catches case, punctuation, whitespace and word-order differences with no
network call. Either way, only answers that scored well are cached, so a bad
answer is never served repeatedly.
"""
import re
import threading

from .embeddings import cosine

_WORD = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> frozenset[str]:
    return frozenset(_WORD.findall((text or "").lower()))


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if not inter:
        return 0.0
    return inter / len(a | b)


class _Entry:
    __slots__ = ("tokens", "vector", "data")

    def __init__(self, tokens, vector, data):
        self.tokens = tokens
        self.vector = vector
        self.data = data


class SemanticCache:
    def __init__(self, max_entries: int = 256, threshold: float = 0.85,
                 semantic_threshold: float = 0.83, min_tokens: int = 4) -> None:
        self.max_entries = max_entries
        self.threshold = threshold                    # lexical (Jaccard)
        self.semantic_threshold = semantic_threshold  # embedding (cosine)
        self.min_tokens = min_tokens
        self._entries: list[_Entry] = []
        self._lock = threading.Lock()

    def lookup(self, text: str, vector: list[float] | None = None) -> dict | None:
        """Best near-duplicate at or above threshold, else None. Uses embedding
        similarity when `vector` is given, otherwise local token overlap.
        Returns {"data", "similarity", "mode"}."""
        toks = _tokens(text)
        if len(toks) < self.min_tokens:
            return None
        best, best_sim = None, 0.0
        semantic = vector is not None
        with self._lock:
            for e in self._entries:
                if semantic and e.vector is not None:
                    sim = cosine(vector, e.vector)
                else:
                    sim = _jaccard(toks, e.tokens)
                if sim > best_sim:
                    best, best_sim = e.data, sim
        bar = self.semantic_threshold if semantic else self.threshold
        if best is not None and best_sim >= bar:
            return {"data": best, "similarity": round(best_sim, 3),
                    "mode": "semantic" if semantic else "lexical"}
        return None

    def store(self, text: str, data: dict, vector: list[float] | None = None) -> None:
        toks = _tokens(text)
        if len(toks) < self.min_tokens:
            return
        with self._lock:
            self._entries.append(_Entry(toks, vector, data))
            if len(self._entries) > self.max_entries:
                self._entries.pop(0)  # FIFO eviction

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)
