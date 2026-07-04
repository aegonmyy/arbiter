"""Core routing-policy behaviour: explore then exploit the cheapest good model,
respect the allowed set, and report measured savings against the baseline."""
import arbiter.policy as policy_mod
from arbiter.policy import MIN_SAMPLES, Policy


def test_choose_only_picks_from_allowed(tmp_path, monkeypatch):
    monkeypatch.setattr(policy_mod.random, "random", lambda: 0.99)
    p = Policy(db_path=str(tmp_path / "p.db"))
    allowed = ["deepseek-v4-flash", "gpt-4o"]
    for _ in range(10):
        d = p.choose("open", allowed=allowed)
        assert d.model in allowed


def test_explores_then_exploits_cheapest_good(tmp_path, monkeypatch):
    monkeypatch.setattr(policy_mod.random, "random", lambda: 0.99)  # no epsilon
    p = Policy(db_path=str(tmp_path / "p.db"))
    cheap, dear = "deepseek-v4-flash", "gpt-4o"
    allowed = [cheap, dear]

    # Both equally good, but one is free and the other expensive.
    for _ in range(MIN_SAMPLES + 1):
        p.record("open", cheap, quality=0.9, cost=0.0, tokens=10)
        p.record("open", dear, quality=0.9, cost=0.02, tokens=10)

    d = p.choose("open", allowed=allowed)
    assert d.mode == "exploit"
    assert d.model == cheap  # same quality, so pick the free one


def test_pays_up_when_only_the_dear_model_is_good(tmp_path, monkeypatch):
    monkeypatch.setattr(policy_mod.random, "random", lambda: 0.99)
    p = Policy(db_path=str(tmp_path / "p.db"))
    cheap, dear = "mistral-small-3.2-24b-instruct-2506", "gpt-4o"
    for _ in range(MIN_SAMPLES + 1):
        p.record("code", cheap, quality=0.2, cost=0.0, tokens=10)   # cheap but bad
        p.record("code", dear, quality=0.95, cost=0.02, tokens=10)  # dear but good
    d = p.choose("code", allowed=[cheap, dear])
    assert d.mode == "exploit"
    assert d.model == dear


def test_report_measures_savings_against_baseline(tmp_path):
    p = Policy(db_path=str(tmp_path / "p.db"))
    # Baseline (gpt-4o) sampled at a real cost; the cheap model serves for free.
    for _ in range(3):
        p.record("math", "gpt-4o", quality=1.0, cost=0.01, tokens=100)
        p.record("math", "deepseek-v4-flash", quality=1.0, cost=0.0, tokens=100)
    rep = p.report()
    assert rep["calls"] == 6
    assert rep["actual_spend"] > 0
    assert rep["saved"] > 0
    assert 0 < rep["saved_pct"] <= 100
