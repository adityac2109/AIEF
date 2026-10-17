"""Leakage checks on the baseline experiment itself."""

import numpy as np
import pandas as pd
import pytest

from bearingguard.data.ims import SealedTestError
from bearingguard.experiments.threshold_baseline import ANY, run, run_bearing

CFG = {
    "tests": [2],
    "calibration_snapshots": 20,
    "features": ["rms", "kurtosis", "crest_factor"],
    "axis": 0,
    "k_sigma": 3.0,
    "sensitivity_k": [3.0],
    "persistence_required": 3,
    "persistence_window": 5,
    "max_operating_gap_s": 3600,
}


def bearing_frame(n=80, seed=0):
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "test_id": 2,
        "timestamp": pd.date_range("2004-02-12", periods=n, freq="10min"),
        "bearing": 1,
        "channel": 1,
        "rms": rng.normal(0.1, 0.005, n),
        "kurtosis": rng.normal(3.5, 0.1, n),
        "crest_factor": rng.normal(4.0, 0.1, n),
    })


def test_future_rows_do_not_change_past_alarms():
    df = bearing_frame()
    altered = df.copy()
    altered.loc[60:, ["rms", "kurtosis", "crest_factor"]] *= 10  # future degradation

    _, a = run_bearing(df, CFG, 3.0)
    _, b = run_bearing(altered, CFG, 3.0)

    cutoff = df["timestamp"].iloc[60]
    pd.testing.assert_frame_equal(a[a["timestamp"] < cutoff], b[b["timestamp"] < cutoff])


def test_calibration_rows_are_not_scored():
    _, tl = run_bearing(bearing_frame(), CFG, 3.0)
    assert len(tl) == 80 - CFG["calibration_snapshots"]
    assert tl["timestamp"].min() == bearing_frame()["timestamp"].iloc[20]


def test_clear_degradation_alarms():
    df = bearing_frame()
    df.loc[70:, "rms"] = 0.3
    res, _ = run_bearing(df, CFG, 3.0)
    by_det = {r["detector"]: r for r in res}
    assert by_det["rms"]["episodes"] >= 1
    assert by_det[ANY]["first_alarm_time"] <= by_det["rms"]["first_alarm_time"]


def test_too_few_snapshots_rejected():
    with pytest.raises(ValueError):
        run_bearing(bearing_frame(n=20), CFG, 3.0)


def test_sealed_test_refused(tmp_path):
    with pytest.raises(SealedTestError):
        run({**CFG, "tests": [3]}, tmp_path)
