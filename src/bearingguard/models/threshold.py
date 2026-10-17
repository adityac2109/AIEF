"""Per-feature k-sigma threshold calibrated on a bearing's own early life."""

from __future__ import annotations

import numpy as np


class ZScoreThreshold:
    """Flags values more than k standard deviations above the calibration mean.

    One-sided because the indicators used here (rms, kurtosis, crest factor)
    increase with developing damage. Statistics come only from the calibration
    rows passed to fit(); scoring a snapshot uses nothing but that snapshot, so
    later data cannot influence earlier scores.
    """

    def __init__(self, k: float):
        self.k = k
        self.mean_: np.ndarray | None = None
        self.std_: np.ndarray | None = None

    def fit(self, calib: np.ndarray) -> "ZScoreThreshold":
        calib = np.asarray(calib, dtype=np.float64)
        if calib.ndim != 2 or calib.shape[0] < 2:
            raise ValueError("calibration data must be 2-D with at least 2 rows")
        std = calib.std(axis=0, ddof=1)
        if np.any(std == 0):
            raise ValueError("a calibration feature has zero variance")
        self.mean_, self.std_ = calib.mean(axis=0), std
        return self

    def score(self, X: np.ndarray) -> np.ndarray:
        if self.mean_ is None:
            raise RuntimeError("fit() must be called before score()")
        return (np.asarray(X, dtype=np.float64) - self.mean_) / self.std_

    def exceed(self, X: np.ndarray) -> np.ndarray:
        return self.score(X) > self.k
