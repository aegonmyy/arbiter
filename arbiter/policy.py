"""The routing brain: learn, per task type, which model to send a request to.

The rule we optimise for is deliberately simple to explain: use the cheapest
model whose measured quality is within a small tolerance of the best model we've
seen for this task. Cheap-but-good wins; we only pay up when nothing cheap is
good enough.

Getting there needs data, so a new task type first explores - every candidate
(including the premium baseline) is tried a few times to learn its quality and
cost from the live runtime. After that we exploit the winner, with a small
random exploration rate so shifting prices or models don't go unnoticed.
"""
import json
import random
import sqlite3
import threading
import time
from dataclasses import dataclass

from .models import BASELINE, CANDIDATES
from .priors import has_prior, prior_quality

# Every model the policy may pick, baseline included - sometimes the expensive
# model really is the only one good enough, and that's a valid choice.
ALL_MODELS = [m.id for m in CANDIDATES] + [BASELINE.id]

MIN_SAMPLES = 2          # tries per model before we trust its numbers
EPSILON = 0.10           # steady-state chance of re-exploring
QUALITY_TOLERANCE = 0.05  # how much quality we'll trade for a cheaper model
PRICE_SHIFT = 0.75       # relative unit-price move that always forces a re-learn
MIN_TOKENS_FOR_PRICE = 40  # ignore price noise until enough tokens are observed
# Variance-aware drift detection: once a model has this many priced calls, a move
# that is both at least REL_FLOOR in relative size and Z_THRESHOLD standard
# deviations from its own price history also triggers a re-learn - so a small but
# consistent shift is caught early, while a noisy price series is not false-flagged.
MIN_PRICE_SAMPLES = 5
REL_FLOOR = 0.10
Z_THRESHOLD = 4.0

# Warm start: a public-benchmark quality prior is folded in as this many
# pseudo-observations, so ~2 real calls outweigh it. A model that carries a prior
# only needs one real sample (to learn its cost) before it can be exploited - the
# prior supplies the quality - which is where cold-start tuition is really spent.
PRIOR_STRENGTH = 1.5


@dataclass
class Decision:
    model: str
    mode: str            # "explore" | "exploit"
    reason: str


class Policy:
    def __init__(self, db_path: str | None = None) -> None:
        import os
        # ARBITER_DB lets a deployment point the store at a mounted volume so
        # learned state survives redeploys.
        db_path = db_path or os.environ.get("ARBITER_DB", "data/arbiter.db")
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._db = sqlite3.connect(db_path, check_same_thread=False)
        self._db.execute("PRAGMA busy_timeout=3000")  # wait rather than error if busy
        self._lock = threading.Lock()
        self._db.execute(
            """CREATE TABLE IF NOT EXISTS stats (
                   task   TEXT,
                   model  TEXT,
                   n      INTEGER NOT NULL DEFAULT 0,
                   q_sum  REAL    NOT NULL DEFAULT 0,
                   cost_sum REAL  NOT NULL DEFAULT 0,
                   tok_sum  REAL  NOT NULL DEFAULT 0,
                   PRIMARY KEY (task, model)
               )"""
        )
        # Migration for older databases that predate token tracking.
        try:
            self._db.execute("ALTER TABLE stats ADD COLUMN tok_sum REAL NOT NULL DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # column already exists
        # Migration for latency tracking (seconds, summed for a per-model mean).
        try:
            self._db.execute("ALTER TABLE stats ADD COLUMN lat_sum REAL NOT NULL DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # column already exists
        # Migration for unit-price statistics (per-call cost/token), used by the
        # variance-aware drift detector: count, sum and sum-of-squares.
        for col in ("up_n", "up_sum", "up_sq"):
            try:
                self._db.execute(f"ALTER TABLE stats ADD COLUMN {col} REAL NOT NULL DEFAULT 0")
            except sqlite3.OperationalError:
                pass  # column already exists
        # Client API keys minted at signup.
        self._db.execute(
            """CREATE TABLE IF NOT EXISTS keys (
                   key     TEXT PRIMARY KEY,
                   email   TEXT,
                   created REAL,
                   status  TEXT NOT NULL DEFAULT 'active'
               )"""
        )
        try:
            self._db.execute("ALTER TABLE keys ADD COLUMN status TEXT NOT NULL DEFAULT 'active'")
        except sqlite3.OperationalError:
            pass  # column already exists
        # One row per routed request, for per-key rate limits.
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS usage (key TEXT, ts REAL)"
        )
        self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_usage_key_ts ON usage (key, ts)"
        )
        # Durable observability: the routing feed, price-shift alerts and the
        # classifier counters used to live only in memory and vanished on every
        # restart. Persisting them here keeps the dashboard populated across
        # redeploys and lets us serve a savings/volume time series.
        self._db.execute(
            """CREATE TABLE IF NOT EXISTS feed (
                   ts REAL, task TEXT, classified_by TEXT, model TEXT, mode TEXT,
                   quality REAL, cost REAL, saved REAL, failover_from TEXT
               )"""
        )
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_feed_ts ON feed (ts)")
        self._db.execute(
            """CREATE TABLE IF NOT EXISTS alerts (
                   ts REAL, task TEXT, model TEXT,
                   old_unit REAL, new_unit REAL, direction TEXT
               )"""
        )
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS counters (name TEXT PRIMARY KEY, value INTEGER NOT NULL DEFAULT 0)"
        )
        self._db.commit()

    # -- client keys -------------------------------------------------------
    def register_key(self, email: str) -> str:
        import secrets
        key = "arb_" + secrets.token_hex(24)
        with self._lock:
            self._db.execute(
                "INSERT INTO keys (key, email, created) VALUES (?, ?, ?)",
                (key, email, time.time()),
            )
            self._db.commit()
        return key

    def is_valid_key(self, key: str) -> bool:
        # Valid for authentication if it exists and is not revoked (paused keys
        # can still authenticate, so a user can resume their own key).
        if not key:
            return False
        with self._lock:
            cur = self._db.execute(
                "SELECT 1 FROM keys WHERE key=? AND status != 'revoked'", (key,))
            return cur.fetchone() is not None

    def key_status(self, key: str) -> str | None:
        with self._lock:
            r = self._db.execute("SELECT status FROM keys WHERE key=?", (key,)).fetchone()
            return r[0] if r else None

    def set_key_status(self, key: str, status: str) -> None:
        with self._lock:
            self._db.execute("UPDATE keys SET status=? WHERE key=?", (status, key))
            self._db.commit()

    def key_info(self, key: str) -> dict | None:
        now = time.time()
        with self._lock:
            r = self._db.execute(
                "SELECT email, created, status FROM keys WHERE key=?", (key,)).fetchone()
            if not r:
                return None
            c6 = self._db.execute(
                "SELECT COUNT(*) FROM usage WHERE key=? AND ts>?", (key, now - 6 * 3600)).fetchone()[0]
            cw = self._db.execute(
                "SELECT COUNT(*) FROM usage WHERE key=? AND ts>?", (key, now - 7 * 86400)).fetchone()[0]
        return {
            "email": r[0], "created": r[1], "status": r[2],
            "used_6h": c6, "limit_6h": self.RATE_6H,
            "used_week": cw, "limit_week": self.RATE_WEEK,
        }

    # Per-key rate limits (minted keys only).
    RATE_6H = 50
    RATE_WEEK = 600

    def try_use(self, key: str) -> tuple[bool, str, int]:
        """Count this request against the key's rolling limits. Returns
        (allowed, limit_hit, retry_after_seconds). Only records on allow."""
        now = time.time()
        w6, ww = now - 6 * 3600, now - 7 * 86400
        with self._lock:
            c6 = self._db.execute(
                "SELECT COUNT(*) FROM usage WHERE key=? AND ts>?", (key, w6)).fetchone()[0]
            if c6 >= self.RATE_6H:
                oldest = self._db.execute(
                    "SELECT MIN(ts) FROM usage WHERE key=? AND ts>?", (key, w6)).fetchone()[0]
                return False, f"{self.RATE_6H} requests per 6 hours", int(oldest + 6 * 3600 - now) + 1
            cw = self._db.execute(
                "SELECT COUNT(*) FROM usage WHERE key=? AND ts>?", (key, ww)).fetchone()[0]
            if cw >= self.RATE_WEEK:
                oldest = self._db.execute(
                    "SELECT MIN(ts) FROM usage WHERE key=? AND ts>?", (key, ww)).fetchone()[0]
                return False, f"{self.RATE_WEEK} requests per week", int(oldest + 7 * 86400 - now) + 1
            self._db.execute("INSERT INTO usage (key, ts) VALUES (?, ?)", (key, now))
            self._db.execute("DELETE FROM usage WHERE ts < ?", (ww,))
            self._db.commit()
            return True, "", 0

    # -- reads -------------------------------------------------------------
    def _row(self, task: str, model: str) -> tuple[int, float, float]:
        cur = self._db.execute(
            "SELECT n, q_sum, cost_sum FROM stats WHERE task=? AND model=?",
            (task, model),
        )
        r = cur.fetchone()
        return (r[0], r[1], r[2]) if r else (0, 0.0, 0.0)

    def _mean(self, task: str, model: str) -> tuple[int, float, float]:
        n, q, c = self._row(task, model)
        if n == 0:
            return 0, 0.0, 0.0
        return n, q / n, c / n

    def baseline_cost(self, task: str) -> float | None:
        n, _, mean_cost = self._mean(task, BASELINE.id)
        return mean_cost if n else None

    def quality_of(self, task: str, model: str) -> float | None:
        n, mean_q, _ = self._mean(task, model)
        return mean_q if n else None

    def cost_of(self, task: str, model: str) -> float | None:
        n, _, mean_cost = self._mean(task, model)
        return mean_cost if n else None

    def latency_of(self, task: str, model: str) -> float | None:
        """Mean measured latency (seconds) for this model on this task, or None
        if we have no timing yet."""
        r = self._db.execute(
            "SELECT n, lat_sum FROM stats WHERE task=? AND model=?", (task, model)
        ).fetchone()
        if not r or not r[0] or not r[1]:
            return None
        return r[1] / r[0]

    def _blended_quality(self, task: str, model: str) -> float | None:
        """Quality estimate used for routing: the measured mean blended with the
        public-benchmark prior via pseudo-counts, so the prior anchors early,
        noisy estimates and decays out as real samples accumulate. Returns None
        only when there is neither data nor a prior."""
        n, q_sum, _ = self._row(task, model)
        prior = prior_quality(task, model)
        if prior is None:
            return (q_sum / n) if n else None
        return (PRIOR_STRENGTH * prior + q_sum) / (PRIOR_STRENGTH + n)

    # -- decision ----------------------------------------------------------
    def choose(self, task: str, allowed: list[str] | None = None) -> Decision:
        # `allowed` is the set of models eligible for this request (e.g. those
        # whose context window fits the prompt). We only ever pick from it.
        pool = [m for m in ALL_MODELS if allowed is None or m in allowed]
        if not pool:                      # nothing fits - fall back to all
            pool = list(ALL_MODELS)

        with self._lock:
            samples = {m: self._row(task, m)[0] for m in pool}

            # 1. Explore: anything not yet sampled enough. A model that carries a
            #    public-benchmark prior only needs one real sample (to learn its
            #    cost) - the prior already supplies a quality estimate - so it
            #    leaves exploration sooner. Pick the least-tried first (prior
            #    quality breaks ties) so exploration spreads and surfaces likely
            #    winners early.
            def need(m: str) -> int:
                return 1 if has_prior(m) else MIN_SAMPLES

            under = [m for m in pool if samples[m] < need(m)]
            if under:
                pick = min(under, key=lambda m: (samples[m], -(prior_quality(task, m) or 0.0)))
                return Decision(pick, "explore", "gathering baseline data")

            # 2. Occasionally re-explore so the policy stays current.
            if random.random() < EPSILON:
                pick = random.choice(pool)
                return Decision(pick, "explore", "epsilon re-check")

            # 3. Exploit: cheapest model within tolerance of the best quality.
            #    Quality is the measured mean blended with the benchmark prior.
            quality = {m: (self._blended_quality(task, m) or 0.0) for m in pool}
            cost = {m: self._mean(task, m)[2] for m in pool}
            best_q = max(quality.values())
            acceptable = {m: cost[m] for m in pool if quality[m] >= best_q - QUALITY_TOLERANCE}
            pick = min(acceptable, key=acceptable.get)
            return Decision(
                pick, "exploit",
                f"cheapest within {QUALITY_TOLERANCE:.2f} of best quality {best_q:.2f}",
            )

    # -- update ------------------------------------------------------------
    def record(self, task: str, model: str, quality: float, cost: float,
               tokens: float = 0, latency: float = 0) -> dict | None:
        """Fold one observation into the model's stats for this task.

        We watch the model's unit price (cost per token) for drift. A move is a
        shift if it is *either* large in relative terms (>= PRICE_SHIFT, the
        original catch-all) *or* statistically significant against the model's own
        price history (>= REL_FLOOR in size and >= Z_THRESHOLD sigma). On a shift
        the stale average is wiped: the model drops back into exploration, is
        re-learned at the new price, and re-routed. Returns the shift, else None.
        """
        unit = (cost / tokens) if tokens > 0 else None
        with self._lock:
            row = self._db.execute(
                "SELECT n, tok_sum, cost_sum, up_n, up_sum, up_sq FROM stats WHERE task=? AND model=?",
                (task, model),
            ).fetchone()

            shift = None
            if (unit is not None and row and row[0] >= MIN_SAMPLES
                    and row[1] >= MIN_TOKENS_FOR_PRICE):
                learned_unit = row[2] / row[1] if row[1] else 0.0
                up_n, up_sum, up_sq = row[3], row[4], row[5]
                if learned_unit > 0:
                    rel = abs(unit - learned_unit) / learned_unit
                    big = rel >= PRICE_SHIFT
                    significant = False
                    if up_n >= MIN_PRICE_SAMPLES and rel >= REL_FLOOR:
                        mean = up_sum / up_n
                        var = max(up_sq / up_n - mean * mean, 0.0)
                        std = var ** 0.5
                        # A near-constant history: any REL_FLOOR-sized move is real.
                        significant = std <= mean * 1e-6 or abs(unit - mean) / std >= Z_THRESHOLD
                    if big or significant:
                        shift = {
                            "task": task, "model": model,
                            "old_unit": learned_unit, "new_unit": unit,
                            "direction": "up" if unit > learned_unit else "down",
                        }

            # Unit-price stats accumulate this observation (0 when no tokens).
            u, u2 = (unit or 0.0), ((unit or 0.0) ** 2)
            up_inc = 1 if unit is not None else 0

            if shift:
                # Re-learn from scratch, seeded with this new-price observation.
                self._db.execute("DELETE FROM stats WHERE task=? AND model=?", (task, model))
                self._db.execute(
                    """INSERT INTO stats
                       (task, model, n, q_sum, cost_sum, tok_sum, lat_sum, up_n, up_sum, up_sq)
                       VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?)""",
                    (task, model, quality, cost, tokens, latency, up_inc, u, u2),
                )
            else:
                self._db.execute(
                    """INSERT INTO stats
                       (task, model, n, q_sum, cost_sum, tok_sum, lat_sum, up_n, up_sum, up_sq)
                       VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(task, model) DO UPDATE SET
                           n = n + 1,
                           q_sum = q_sum + excluded.q_sum,
                           cost_sum = cost_sum + excluded.cost_sum,
                           tok_sum = tok_sum + excluded.tok_sum,
                           lat_sum = lat_sum + excluded.lat_sum,
                           up_n = up_n + excluded.up_n,
                           up_sum = up_sum + excluded.up_sum,
                           up_sq = up_sq + excluded.up_sq""",
                    (task, model, quality, cost, tokens, latency, up_inc, u, u2),
                )
            self._db.commit()
            return shift

    def reset(self) -> None:
        """Wipe learned state - handy for a clean demo run."""
        with self._lock:
            self._db.execute("DELETE FROM stats")
            self._db.commit()

    # -- reporting ---------------------------------------------------------
    def report(self) -> dict:
        """Cumulative savings vs. running everything on the baseline.

        Actual spend is exact (summed runtime charges). The baseline-equivalent
        is each call re-priced at the baseline's measured mean cost for its task
        type, so savings are grounded in real numbers, not list prices. Tasks
        where we haven't sampled the baseline claim no savings."""
        cur = self._db.execute("SELECT task, model, n, cost_sum FROM stats")
        base_mean: dict[str, float] = {}
        task_calls: dict[str, int] = {}
        task_spend: dict[str, float] = {}
        for task, model, n, cost_sum in cur.fetchall():
            task_calls[task] = task_calls.get(task, 0) + n
            task_spend[task] = task_spend.get(task, 0.0) + cost_sum
            if model == BASELINE.id and n:
                base_mean[task] = cost_sum / n

        actual = sum(task_spend.values())
        baseline_equiv = 0.0
        for task, calls in task_calls.items():
            if task in base_mean:
                baseline_equiv += calls * base_mean[task]
            else:
                baseline_equiv += task_spend[task]  # no baseline data -> no claim
        saved = baseline_equiv - actual
        pct = (saved / baseline_equiv * 100) if baseline_equiv else 0.0
        return {
            "calls": sum(task_calls.values()),
            "actual_spend": round(actual, 8),
            "baseline_spend": round(baseline_equiv, 8),
            "saved": round(saved, 8),
            "saved_pct": round(pct, 1),
        }

    def snapshot(self) -> dict:
        cur = self._db.execute(
            "SELECT task, model, n, q_sum, cost_sum, lat_sum FROM stats ORDER BY task, model"
        )
        tasks: dict[str, list[dict]] = {}
        for task, model, n, q_sum, cost_sum, lat_sum in cur.fetchall():
            tasks.setdefault(task, []).append({
                "model": model,
                "n": n,
                "quality": round(q_sum / n, 3) if n else None,
                "avg_cost": round(cost_sum / n, 8) if n else None,
                "avg_latency_ms": round(lat_sum / n * 1000) if n and lat_sum else None,
            })
        return tasks

    # -- durable metrics ---------------------------------------------------
    FEED_KEEP = 500   # rows of routing feed to retain
    ALERTS_KEEP = 100  # rows of price-shift alerts to retain

    def add_event(self, ev: dict) -> None:
        """Persist one routing decision to the feed (newest kept, old pruned)."""
        with self._lock:
            self._db.execute(
                """INSERT INTO feed
                   (ts, task, classified_by, model, mode, quality, cost, saved, failover_from)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (ev["ts"], ev["task"], ev["classified_by"], ev["model"], ev["mode"],
                 ev["quality"], ev["cost"], ev.get("saved"),
                 json.dumps(ev.get("failover_from")) if ev.get("failover_from") else None),
            )
            self._db.execute(
                "DELETE FROM feed WHERE rowid NOT IN "
                "(SELECT rowid FROM feed ORDER BY ts DESC LIMIT ?)", (self.FEED_KEEP,))
            self._db.commit()

    def recent_events(self, limit: int = 25) -> list[dict]:
        cur = self._db.execute(
            """SELECT ts, task, classified_by, model, mode, quality, cost, saved, failover_from
               FROM feed ORDER BY ts DESC LIMIT ?""", (limit,))
        out = []
        for r in cur.fetchall():
            out.append({
                "ts": r[0], "task": r[1], "classified_by": r[2], "model": r[3],
                "mode": r[4], "quality": r[5], "cost": r[6], "saved": r[7],
                "failover_from": json.loads(r[8]) if r[8] else None,
            })
        return out

    def add_alert(self, a: dict) -> None:
        with self._lock:
            self._db.execute(
                "INSERT INTO alerts (ts, task, model, old_unit, new_unit, direction) VALUES (?, ?, ?, ?, ?, ?)",
                (a.get("ts", time.time()), a["task"], a["model"],
                 a["old_unit"], a["new_unit"], a["direction"]))
            self._db.execute(
                "DELETE FROM alerts WHERE rowid NOT IN "
                "(SELECT rowid FROM alerts ORDER BY ts DESC LIMIT ?)", (self.ALERTS_KEEP,))
            self._db.commit()

    def recent_alerts(self, limit: int = 25) -> list[dict]:
        cur = self._db.execute(
            "SELECT ts, task, model, old_unit, new_unit, direction FROM alerts ORDER BY ts DESC LIMIT ?",
            (limit,))
        return [{"ts": r[0], "task": r[1], "model": r[2], "old_unit": r[3],
                 "new_unit": r[4], "direction": r[5]} for r in cur.fetchall()]

    def alert_count(self) -> int:
        return self._db.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]

    def bump_counter(self, name: str) -> None:
        with self._lock:
            self._db.execute(
                "INSERT INTO counters (name, value) VALUES (?, 1) "
                "ON CONFLICT(name) DO UPDATE SET value = value + 1", (name,))
            self._db.commit()

    def counters(self) -> dict:
        cur = self._db.execute("SELECT name, value FROM counters")
        d = {r[0]: r[1] for r in cur.fetchall()}
        for k in ("rules", "model", "model-fallback"):
            d.setdefault(k, 0)
        return d

    def timeseries(self, bucket_seconds: int = 3600, buckets: int = 24) -> list[dict]:
        """Calls and spend per time bucket over the recent window, oldest first,
        for a dashboard trend line. Bounded by what the feed retains."""
        now = time.time()
        start = now - bucket_seconds * buckets
        cur = self._db.execute("SELECT ts, cost FROM feed WHERE ts >= ?", (start,))
        agg: dict[int, dict] = {}
        for ts, cost in cur.fetchall():
            b = int((ts - start) // bucket_seconds)
            if b < 0 or b >= buckets:
                continue
            a = agg.setdefault(b, {"calls": 0, "spend": 0.0})
            a["calls"] += 1
            a["spend"] += cost or 0.0
        return [{
            "bucket_start": round(start + i * bucket_seconds),
            "calls": agg.get(i, {}).get("calls", 0),
            "spend": round(agg.get(i, {}).get("spend", 0.0), 8),
        } for i in range(buckets)]

    def clear_metrics(self) -> None:
        with self._lock:
            for t in ("feed", "alerts", "counters"):
                self._db.execute(f"DELETE FROM {t}")
            self._db.commit()
