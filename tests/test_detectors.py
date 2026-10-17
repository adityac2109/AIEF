import numpy as np
import pytest

from bearingguard.models.isolation_forest import IsolationForestScorer
from bearingguard.models.recalibration import recenter_features, recentered_scores
from bearingguard.models.thresholds import (
    calibration_pvalues,
    ksigma_exceed,
    pvalue_exceed,
)

RNG = np.random.default_rng(0)


def test_iforest_scores_outliers_higher():
    X = RNG.normal(size=(200, 3))
    m = IsolationForestScorer(seed=0).fit(X)
    inlier, outlier = m.score(np.zeros((1, 3))), m.score(np.full((1, 3), 6.0))
    assert outlier[0] > inlier[0]


def test_iforest_is_deterministic_for_a_seed():
    X = RNG.normal(size=(100, 3))
    a = IsolationForestScorer(seed=7).fit(X).score(X)
    b = IsolationForestScorer(seed=7).fit(X).score(X)
    np.testing.assert_array_equal(a, b)


def test_iforest_rejects_constant_feature_and_unfitted_use():
    with pytest.raises(ValueError):
        IsolationForestScorer().fit(np.column_stack([RNG.normal(size=10), np.ones(10)]))
    with pytest.raises(RuntimeError):
        IsolationForestScorer().score(np.zeros((1, 2)))


def test_pvalues_match_definition():
    cal = np.array([1.0, 2.0, 3.0, 4.0])
    p = calibration_pvalues(np.array([0.5, 2.0, 4.5, np.nan]), cal)
    np.testing.assert_allclose(p[:3], [5 / 5, 4 / 5, 1 / 5])
    assert np.isnan(p[3])


def test_pvalues_are_marginally_valid_under_exchangeability():
    # The guarantee P(p <= alpha) <= alpha is marginal over the calibration draw.
    # For one fixed calibration set the rate is Beta-distributed around alpha
    # (sd ~0.02 for n=99), so average over many independent calibration sets.
    rng = np.random.default_rng(1)
    for alpha in (0.05, 0.1):
        rates = [pvalue_exceed(rng.normal(size=200), rng.normal(size=99), alpha).mean()
                 for _ in range(2_000)]
        assert np.mean(rates) <= alpha + 0.005


def test_pvalue_alpha_below_resolution_rejected():
    with pytest.raises(ValueError, match="smallest attainable"):
        pvalue_exceed(np.zeros(3), np.arange(10.0), alpha=0.05)


def test_ksigma_exceed_and_nan_handling():
    cal = np.array([0.0, 1.0, 2.0])  # mean 1, sd 1
    assert ksigma_exceed(np.array([3.9, 4.1, np.nan]), cal, k=3).tolist() == [False, True, False]
    with pytest.raises(ValueError):
        ksigma_exceed(np.zeros(2), np.ones(3), k=3)


def ts(minutes):
    return np.datetime64("2003-10-22T12:00:00") + np.array(minutes, dtype="timedelta64[m]")


def test_recenter_features_removes_session_offset_causally():
    minutes = list(range(0, 300, 10)) + list(range(3000, 3300, 10))
    X = np.r_[np.zeros((30, 2)), np.full((30, 2), 5.0)]
    X_adj, window = recenter_features(X, ts(minutes), n_initial=10, n_restart=5, restart_gap_s=8 * 3600)
    np.testing.assert_allclose(X_adj[30:], 0.0)
    assert window[30:35].all() and window.sum() == 5
    X2 = X.copy()
    X2[40:] += 99  # later rows of the session do not change the shift
    np.testing.assert_allclose(recenter_features(X2, ts(minutes), 10, 5, 8 * 3600)[0][30:40], 0.0)


def test_recentered_scores_equal_zscore_of_recentered_features():
    minutes = list(range(0, 400, 10)) + list(range(3000, 3400, 10))
    X = RNG.normal(size=(80, 2))
    X[40:] += 3
    z, scored = recentered_scores(X, ts(minutes), 20, 5, 8 * 3600)
    X_adj, _ = recenter_features(X, ts(minutes), 20, 5, 8 * 3600)
    expected = (X_adj - X[:20].mean(0)) / X[:20].std(0, ddof=1)
    np.testing.assert_allclose(z[scored], expected[scored])
