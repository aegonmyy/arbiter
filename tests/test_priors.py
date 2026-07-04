"""Warm-start priors: benchmark quality anchors early estimates and decays as
real data arrives, and a model with a prior leaves exploration after one sample."""
import arbiter.policy as policy_mod
from arbiter.policy import PRIOR_STRENGTH, Policy
from arbiter.priors import has_prior, prior_quality


def _policy(tmp_path):
    return Policy(db_path=str(tmp_path / "p.db"))


def test_blended_quality_anchors_to_prior_then_decays(tmp_path):
    p = _policy(tmp_path)
    model, task = "deepseek-v4-flash", "code"
    prior = prior_quality(task, model)
    assert prior is not None

    # No data yet: estimate is exactly the prior.
    assert abs(p._blended_quality(task, model) - prior) < 1e-9

    # One real observation of quality 1.0: prior still pulls it down a bit.
    p.record(task, model, quality=1.0, cost=0.0, tokens=5)
    expected = (PRIOR_STRENGTH * prior + 1.0) / (PRIOR_STRENGTH + 1)
    assert abs(p._blended_quality(task, model) - expected) < 1e-9

    # Many observations: the prior washes out, estimate approaches the data.
    for _ in range(50):
        p.record(task, model, quality=1.0, cost=0.0, tokens=5)
    assert p._blended_quality(task, model) > 0.99


def test_model_with_prior_exploits_after_one_sample(tmp_path, monkeypatch):
    # Skip the epsilon re-check so the assertion is deterministic.
    monkeypatch.setattr(policy_mod.random, "random", lambda: 0.99)
    p = _policy(tmp_path)
    model, task = "deepseek-v4-flash", "code"
    assert has_prior(model)

    # First choice among just this model must explore (no data at all).
    assert p.choose(task, allowed=[model]).mode == "explore"
    # After a single sample, the prior supplies quality, so it can exploit.
    p.record(task, model, quality=1.0, cost=0.0, tokens=5)
    assert p.choose(task, allowed=[model]).mode == "exploit"


def test_unknown_model_has_no_prior(tmp_path):
    assert prior_quality("code", "no-such-model") is None
    assert not has_prior("no-such-model")
    p = _policy(tmp_path)
    # With no prior and no data, the blended estimate is undefined (None).
    assert p._blended_quality("code", "no-such-model") is None
