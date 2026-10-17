"""Re-center a k-sigma detector after long rig shutdowns.

IMS test 1 shows a simultaneous level shift on all bearings after a 148 h
shutdown, so a baseline taken before the stop no longer describes normal
running afterwards. After every gap of at least restart_gap_s, the first
n_restart snapshots of the new session re-estimate the feature means and are
not scored. The standard deviations keep their initial-calibration values: the
observed problem is a level shift, and a few hours of data estimate spread
poorly.

Trade-off: re-centering also absorbs any degradation that accumulated across
the shutdown, so slow damage that spans sessions can be masked.
"""

from __future__ import annotations

import numpy as np

from bearingguard.models.threshold import ZScoreThreshold


def session_starts(timestamps: np.ndarray, restart_gap_s: float) -> np.ndarray:
    """Indices of the first snapshot after each gap >= restart_gap_s."""
    t = np.asarray(timestamps, dtype="datetime64[s]").astype(np.int64)
    return np.flatnonzero(np.diff(t) >= restart_gap_s) + 1


def recentered_scores(X: np.ndarray, timestamps: np.ndarray, n_initial: int,
                      n_restart: int, restart_gap_s: float) -> tuple[np.ndarray, np.ndarray]:
    """Return (z, scored): z-scores for every row and a mask of scored rows.

    Rows used for any calibration are unscored (z = NaN). Each row's score uses
    only calibration rows that precede it, so the procedure is causal.
    """
    X = np.asarray(X, dtype=np.float64)
    base = ZScoreThreshold(k=np.inf).fit(X[:n_initial])
    mean = np.tile(base.mean_, (len(X), 1))
    scored = np.zeros(len(X), dtype=bool)
    scored[n_initial:] = True

    for s in session_starts(timestamps, restart_gap_s):
        if s < n_initial:
            continue  # the shutdown falls inside the initial calibration window
        window = slice(s, min(s + n_restart, len(X)))
        mean[s:] = X[window].mean(axis=0)
        scored[window] = False

    z = (X - mean) / base.std_
    z[~scored] = np.nan
    return z, scored
