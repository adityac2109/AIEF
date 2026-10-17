"""Time-domain condition indicators computed on one 1 s snapshot channel.

These are the standard bearing condition indicators:
- rms: overall vibration energy; rises as damage spreads.
- kurtosis (Pearson, Gaussian = 3): impulsiveness; rises when an early local
  defect produces periodic impacts, and often falls again as damage spreads and
  the signal becomes broadband.
- crest_factor (peak / rms): another impulsiveness measure, less tail-sensitive.
- skewness, std, peak, peak_to_peak: reported for analysis.

Each value is computed from the snapshot alone, so a feature can never carry
information from other snapshots.
"""

from __future__ import annotations

import numpy as np

FEATURE_NAMES = ("rms", "std", "peak", "peak_to_peak", "crest_factor", "kurtosis", "skewness")


def time_domain_features(x: np.ndarray) -> dict[str, float]:
    x = np.asarray(x, dtype=np.float64)
    if x.ndim != 1 or x.size < 2:
        raise ValueError("expected a 1-D signal with at least 2 samples")

    centered = x - x.mean()
    var = np.mean(centered**2)
    if var == 0.0:
        # Shape statistics are undefined for a constant signal. Validation
        # should have excluded such files; fail loudly rather than emit NaN.
        raise ValueError("constant signal: kurtosis/skewness undefined")
    std = np.sqrt(var)
    rms = np.sqrt(np.mean(x**2))
    peak = np.max(np.abs(x))
    return {
        "rms": float(rms),
        "std": float(std),
        "peak": float(peak),
        "peak_to_peak": float(x.max() - x.min()),
        "crest_factor": float(peak / rms),
        "kurtosis": float(np.mean(centered**4) / var**2),
        "skewness": float(np.mean(centered**3) / std**3),
    }
