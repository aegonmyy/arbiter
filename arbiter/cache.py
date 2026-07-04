"""A lightweight near-duplicate response cache.

The cheapest call is the one you never make. When a prompt is a near-duplicate of
one we've already answered well, we can serve the stored answer for free instead
of routing it to a model at all. This complements the runtime's own exact cache:
that keys on byte-for-byte identical inputs, whereas this tolerates differences in
case, punctuation, whitespace and word order.

The similarity here is deliberately simple and local - token-set (Jaccard)
overlap of the normalized prompt, no embeddings and no network call, so it adds
almost nothing to the hot path. It catches true near-duplicates (the same words,
lightly reworded); genuinely semantic matching (paraphrases with different words)
is the embedding-based upgrade noted in the roadmap. We only cache answers that
scored well, so a bad answer is never served repeatedly.
"""
import re
import threading

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


class SemanticCache:
    def __init__(self, max_entries: int = 256, threshold: float = 0.85,
                 min_tokens: int = 4) -> None:
        self.max_entries = max_entries
        self.threshold = threshold
        self.min_tokens = min_tokens
        self._entries: list[tuple[frozenset[str], dict]] = []
        self._lock = threading.Lock()

    def lookup(self, text: str) -> dict | None:
        """Return {"data": ..., "similarity": ...} for the best near-duplicate at
        or above the threshold, else None."""
        toks = _tokens(text)
        if len(toks) < self.min_tokens:
            return None
        best, best_sim = None, 0.0
        with self._lock:
            for tset, data in self._entries:
                sim = _jaccard(toks, tset)
                if sim > best_sim:
                    best, best_sim = data, sim
        if best is not None and best_sim >= self.threshold:
            return {"data": best, "similarity": round(best_sim, 3)}
        return None

    def store(self, text: str, data: dict) -> None:
        toks = _tokens(text)
        if len(toks) < self.min_tokens:
            return
        with self._lock:
            self._entries.append((toks, data))
            if len(self._entries) > self.max_entries:
                self._entries.pop(0)  # FIFO eviction

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)
