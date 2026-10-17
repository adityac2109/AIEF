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


def recenter_features(X: np.ndarray, timestamps: np.ndarray, n_initial: int,
                      n_restart: int, restart_gap_s: float) -> tuple[np.ndarray, np.ndarray]:
    """Shift each post-restart session back to the initial calibration mean.

    Returns (X_adj, restart_window): rows of a session after a restart become
    x - mean(restart window) + mean(initial calibration), and restart_window
    marks the rows used to estimate the session mean (these must not be scored).
    Each shift uses only rows at the start of its own session, which precede
    every row it is applied to, so the transform is causal. Any detector can
    then run on X_adj unchanged.
    """
    X = np.asarray(X, dtype=np.float64)
    initial_mean = X[:n_initial].mean(axis=0)
    offset = np.zeros_like(X)
    restart_window = np.zeros(len(X), dtype=bool)
    for s in session_starts(timestamps, restart_gap_s):
        if s < n_initial:
            continue  # the shutdown falls inside the initial calibration window
        window = slice(s, min(s + n_restart, len(X)))
        offset[s:] = X[window].mean(axis=0) - initial_mean
        restart_window[window] = True
    return X - offset, restart_window


def recentered_scores(X: np.ndarray, timestamps: np.ndarray, n_initial: int,
                      n_restart: int, restart_gap_s: float) -> tuple[np.ndarray, np.ndarray]:
    """Return (z, scored): z-scores for every row and a mask of scored rows.

    Rows used for any calibration are unscored (z = NaN). Each row's score uses
    only calibration rows that precede it, so the procedure is causal.
    """
    X = np.asarray(X, dtype=np.float64)
    X_adj, restart_window = recenter_features(X, timestamps, n_initial, n_restart, restart_gap_s)
    base = ZScoreThreshold(k=np.inf).fit(X[:n_initial])
    scored = ~restart_window
    scored[:n_initial] = False
    z = base.score(X_adj)
    z[~scored] = np.nan
    return z, scored
