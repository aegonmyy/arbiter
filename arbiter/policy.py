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
import random
import sqlite3
import threading
from dataclasses import dataclass

from .models import BASELINE, CANDIDATES

# Every model the policy may pick, baseline included - sometimes the expensive
# model really is the only one good enough, and that's a valid choice.
ALL_MODELS = [m.id for m in CANDIDATES] + [BASELINE.id]

MIN_SAMPLES = 2          # tries per model before we trust its numbers
EPSILON = 0.10           # steady-state chance of re-exploring
QUALITY_TOLERANCE = 0.05  # how much quality we'll trade for a cheaper model
PRICE_SHIFT = 0.75       # unit-price move that forces a model to be re-learned
MIN_TOKENS_FOR_PRICE = 40  # ignore price noise until enough tokens are observed


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
        self._db.commit()

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

    # -- decision ----------------------------------------------------------
    def choose(self, task: str, allowed: list[str] | None = None) -> Decision:
        # `allowed` is the set of models eligible for this request (e.g. those
        # whose context window fits the prompt). We only ever pick from it.
        pool = [m for m in ALL_MODELS if allowed is None or m in allowed]
        if not pool:                      # nothing fits - fall back to all
            pool = list(ALL_MODELS)

        with self._lock:
            samples = {m: self._row(task, m)[0] for m in pool}

            # 1. Explore: anything not yet sampled enough. Pick the least-tried
            #    so exploration spreads evenly.
            under = [m for m in pool if samples[m] < MIN_SAMPLES]
            if under:
                pick = min(under, key=lambda m: samples[m])
                return Decision(pick, "explore", "gathering baseline data")

            # 2. Occasionally re-explore so the policy stays current.
            if random.random() < EPSILON:
                pick = random.choice(pool)
                return Decision(pick, "explore", "epsilon re-check")

            # 3. Exploit: cheapest model within tolerance of the best quality.
            means = {m: self._mean(task, m) for m in pool}
            best_q = max(mq for _, mq, _ in means.values())
            acceptable = {
                m: mc for m, (_, mq, mc) in means.items()
                if mq >= best_q - QUALITY_TOLERANCE
            }
            pick = min(acceptable, key=acceptable.get)
            return Decision(
                pick, "exploit",
                f"cheapest within {QUALITY_TOLERANCE:.2f} of best quality {best_q:.2f}",
            )

    # -- update ------------------------------------------------------------
    def record(self, task: str, model: str, quality: float, cost: float,
               tokens: float = 0) -> dict | None:
        """Fold one observation into the model's stats for this task.

        We watch the model's unit price (cost per token). If it moves more than
        PRICE_SHIFT from what we'd learned, the old average is stale, so we wipe
        this model's memory for the task - it drops back into exploration and is
        re-learned at the new price, then re-routed accordingly. Returns a
        description of the shift when one happens, else None.
        """
        with self._lock:
            cur = self._db.execute(
                "SELECT n, tok_sum, cost_sum FROM stats WHERE task=? AND model=?",
                (task, model),
            )
            row = cur.fetchone()

            shift = None
            if (row and tokens > 0 and row[0] >= MIN_SAMPLES
                    and row[1] >= MIN_TOKENS_FOR_PRICE):
                learned_unit = row[2] / row[1]
                new_unit = cost / tokens
                if learned_unit > 0 and abs(new_unit - learned_unit) / learned_unit > PRICE_SHIFT:
                    shift = {
                        "task": task, "model": model,
                        "old_unit": learned_unit, "new_unit": new_unit,
                        "direction": "up" if new_unit > learned_unit else "down",
                    }

            if shift:
                self._db.execute("DELETE FROM stats WHERE task=? AND model=?", (task, model))
                self._db.execute(
                    "INSERT INTO stats (task, model, n, q_sum, cost_sum, tok_sum) VALUES (?, ?, 1, ?, ?, ?)",
                    (task, model, quality, cost, tokens),
                )
            else:
                self._db.execute(
                    """INSERT INTO stats (task, model, n, q_sum, cost_sum, tok_sum)
                       VALUES (?, ?, 1, ?, ?, ?)
                       ON CONFLICT(task, model) DO UPDATE SET
                           n = n + 1,
                           q_sum = q_sum + excluded.q_sum,
                           cost_sum = cost_sum + excluded.cost_sum,
                           tok_sum = tok_sum + excluded.tok_sum""",
                    (task, model, quality, cost, tokens),
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
            "SELECT task, model, n, q_sum, cost_sum FROM stats ORDER BY task, model"
        )
        tasks: dict[str, list[dict]] = {}
        for task, model, n, q_sum, cost_sum in cur.fetchall():
            tasks.setdefault(task, []).append({
                "model": model,
                "n": n,
                "quality": round(q_sum / n, 3) if n else None,
                "avg_cost": round(cost_sum / n, 8) if n else None,
            })
        return tasks
