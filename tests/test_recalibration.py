import numpy as np
import pytest

from bearingguard.models.recalibration import recentered_scores, session_starts


def timestamps(minutes):
    return np.datetime64("2003-10-22T12:00:00") + np.array(minutes, dtype="timedelta64[m]")


def series_with_restart(n_before=60, n_after=40, shift=1.0, seed=0):
    """10-min snapshots, a 48 h shutdown, then a level shift on restart."""
    rng = np.random.default_rng(seed)
    minutes = list(range(0, 10 * n_before, 10))
    restart = minutes[-1] + 48 * 60
    minutes += list(range(restart, restart + 10 * n_after, 10))
    X = rng.normal(0, 0.1, size=(n_before + n_after, 1))
    X[n_before:] += shift
    return X, timestamps(minutes)


def test_session_starts_finds_long_gaps_only():
    t = timestamps([0, 10, 20, 90, 100, 1000])  # 70 min and 15 h gaps
    assert session_starts(t, restart_gap_s=3600).tolist() == [3, 5]
    assert session_starts(t, restart_gap_s=8 * 3600).tolist() == [5]
    assert session_starts(t, restart_gap_s=24 * 3600).tolist() == []


def test_level_shift_after_restart_is_removed():
    X, t = series_with_restart(shift=1.0)
    z, scored = recentered_scores(X, t, n_initial=30, n_restart=10, restart_gap_s=8 * 3600)

    assert not scored[:30].any() and not scored[60:70].any() and scored[70:].all()
    assert np.nanmax(np.abs(z[70:])) < 5  # shift is 10 sigma without re-centering


def test_spread_is_kept_from_initial_calibration():
    X, t = series_with_restart(shift=0.0)
    X[60:] *= 5  # more variable after restart, same mean
    z, _ = recentered_scores(X, t, n_initial=30, n_restart=10, restart_gap_s=8 * 3600)
    # Using the initial (small) sigma, the larger post-restart variation stays visible.
    assert np.nanmax(np.abs(z[70:])) > 5


def test_rows_before_restart_are_unaffected_by_later_data():
    X, t = series_with_restart()
    z1, _ = recentered_scores(X, t, 30, 10, 8 * 3600)
    X2 = X.copy()
    X2[60:] += 100
    z2, _ = recentered_scores(X2, t, 30, 10, 8 * 3600)
    np.testing.assert_array_equal(z1[:60], z2[:60])


def test_gap_inside_initial_calibration_is_ignored():
    X, t = series_with_restart(n_before=20, n_after=40, shift=0.0)
    z, scored = recentered_scores(X, t, n_initial=30, n_restart=10, restart_gap_s=8 * 3600)
    assert not scored[:30].any() and scored[30:].all()


def test_without_restarts_matches_plain_zscore():
    rng = np.random.default_rng(3)
    X = rng.normal(size=(50, 2))
    t = timestamps(range(0, 500, 10))
    z, scored = recentered_scores(X, t, 20, 5, 8 * 3600)
    expected = (X[20:] - X[:20].mean(0)) / X[:20].std(0, ddof=1)
    np.testing.assert_allclose(z[20:], expected)
    assert scored[20:].all()
