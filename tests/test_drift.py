"""Variance-aware price-drift detection.

Unit price = cost / tokens. We drive it precisely by fixing tokens=100 and
setting cost = unit * 100.
"""
from arbiter.policy import Policy

TOK = 100


def _rec(p, unit, task="math", model="deepseek-chat-v3"):
    return p.record(task, model, quality=0.9, cost=unit * TOK, tokens=TOK)


def test_large_move_always_triggers(tmp_path):
    p = Policy(db_path=str(tmp_path / "p.db"))
    for _ in range(6):
        assert _rec(p, 1e-3) is None
    shift = _rec(p, 5e-3)  # 5x jump - the relative catch-all fires
    assert shift is not None
    assert shift["direction"] == "up"


def test_small_but_consistent_move_now_triggers(tmp_path):
    # A stable price history (near-zero variance) followed by a 25% move: below
    # the old fixed 0.75 threshold, but many sigma against the model's own
    # history, so the variance-aware test catches it early.
    p = Policy(db_path=str(tmp_path / "p.db"))
    for _ in range(6):
        assert _rec(p, 1e-3) is None
    shift = _rec(p, 1.25e-3)
    assert shift is not None
    assert shift["direction"] == "up"


def test_in_band_noise_does_not_false_alarm(tmp_path):
    # A genuinely noisy price series (+/-20%). A 25% probe is within its normal
    # spread (~1.25 sigma), so it must NOT be flagged as a shift.
    p = Policy(db_path=str(tmp_path / "p.db"))
    noisy = [0.8e-3, 1.2e-3, 0.8e-3, 1.2e-3, 0.8e-3, 1.2e-3]
    for u in noisy:
        assert _rec(p, u) is None
    assert _rec(p, 1.25e-3) is None


def test_free_model_never_triggers(tmp_path):
    # Zero-cost models have unit price 0; drift detection must skip them.
    p = Policy(db_path=str(tmp_path / "p.db"))
    for _ in range(6):
        assert _rec(p, 0.0) is None
    assert _rec(p, 0.0) is None
