"""Isolation Forest anomaly score, fitted on one bearing's calibration rows.

Features are standardized with the fit rows' mean and standard deviation so
that no single feature dominates the random splits. The anomaly score is
-score_samples (higher = more anomalous). No contamination parameter is used:
thresholds are set separately from held-out calibration scores
(see models.thresholds), because scores on the rows the forest was fitted on
are optimistically low.
"""

from __future__ import annotations

import numpy as np
from sklearn.ensemble import IsolationForest


class IsolationForestScorer:
    def __init__(self, n_estimators: int = 200, seed: int = 0):
        self.n_estimators = n_estimators
        self.seed = seed
        self._forest: IsolationForest | None = None

    def fit(self, X: np.ndarray) -> "IsolationForestScorer":
        X = np.asarray(X, dtype=np.float64)
        if X.ndim != 2 or len(X) < 2:
            raise ValueError("need a 2-D fit set with at least 2 rows")
        self.mean_ = X.mean(axis=0)
        self.std_ = X.std(axis=0, ddof=1)
        if np.any(self.std_ == 0):
            raise ValueError("a fit feature has zero variance")
        self._forest = IsolationForest(
            n_estimators=self.n_estimators,
            max_samples=min(256, len(X)),
            random_state=self.seed,
        ).fit((X - self.mean_) / self.std_)
        return self

    def score(self, X: np.ndarray) -> np.ndarray:
        if self._forest is None:
            raise RuntimeError("fit() must be called before score()")
        return -self._forest.score_samples((np.asarray(X, dtype=np.float64) - self.mean_) / self.std_)
