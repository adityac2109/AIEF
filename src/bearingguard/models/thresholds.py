"""Turn a scalar anomaly score into per-snapshot exceedances.

Both rules use only scores of held-out calibration snapshots (healthy-period
rows that the scorer was *not* fitted on).

k-sigma
    exceed when (s - mean(cal)) / std(cal) > k.

Calibration p-value (split-conformal form)
    p(s) = (1 + #{cal >= s}) / (n_cal + 1); exceed when p <= alpha.
    If the new score and the calibration scores are exchangeable (for example
    i.i.d. draws from the same healthy distribution), then P(p <= alpha) <= alpha
    for each snapshot. Vibration snapshots are autocorrelated, the rig drifts
    and restarts, and the calibration rows come from one early time window, so
    exchangeability is *not* assumed here. Whether the nominal rate holds is
    measured empirically (experiments.detect, "validity" output). With n_cal
    scores the smallest attainable p is 1 / (n_cal + 1).
"""

from __future__ import annotations

import numpy as np


def ksigma_exceed(scores: np.ndarray, cal_scores: np.ndarray, k: float) -> np.ndarray:
    cal = np.asarray(cal_scores, dtype=np.float64)
    sd = cal.std(ddof=1)
    if not np.isfinite(sd) or sd == 0:
        raise ValueError("calibration scores need at least 2 distinct values")
    with np.errstate(invalid="ignore"):
        return (np.asarray(scores, dtype=np.float64) - cal.mean()) / sd > k


def calibration_pvalues(scores: np.ndarray, cal_scores: np.ndarray) -> np.ndarray:
    cal = np.sort(np.asarray(cal_scores, dtype=np.float64))
    s = np.asarray(scores, dtype=np.float64)
    n_ge = len(cal) - np.searchsorted(cal, s, side="left")
    p = (1.0 + n_ge) / (len(cal) + 1.0)
    p[np.isnan(s)] = np.nan
    return p


def pvalue_exceed(scores: np.ndarray, cal_scores: np.ndarray, alpha: float) -> np.ndarray:
    min_p = 1.0 / (len(cal_scores) + 1)
    if alpha < min_p - 1e-12:
        raise ValueError(f"alpha={alpha} is below the smallest attainable p-value {min_p:.4f}")
    p = calibration_pvalues(scores, cal_scores)
    with np.errstate(invalid="ignore"):
        return p <= alpha + 1e-12
