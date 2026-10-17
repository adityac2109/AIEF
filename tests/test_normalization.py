import numpy as np
import pandas as pd
import pytest

from bearingguard.preprocessing.normalization import cross_bearing_log_ratio


def frame(values):
    """values: {bearing: [feature value per timestamp]}"""
    n = len(next(iter(values.values())))
    t = pd.date_range("2004-02-12", periods=n, freq="10min")
    return pd.DataFrame([
        {"timestamp": t[i], "bearing": b, "rms": v[i]}
        for b, v in values.items() for i in range(n)
    ])


def test_common_mode_gain_change_cancels():
    base = {1: [1.0, 1.0], 2: [2.0, 2.0], 3: [1.5, 1.5], 4: [0.5, 0.5]}
    shifted = {b: [v[0], v[1] * 1.2] for b, v in base.items()}  # +20% on every bearing
    out = cross_bearing_log_ratio(frame(shifted), ["rms"])
    first = out[out["timestamp"] == out["timestamp"].min()].set_index("bearing")["rms"]
    second = out[out["timestamp"] == out["timestamp"].max()].set_index("bearing")["rms"]
    pd.testing.assert_series_equal(first, second, check_names=False)


def test_single_bearing_increase_is_preserved():
    out = cross_bearing_log_ratio(frame({1: [1.0, 3.0], 2: [1.0, 1.0], 3: [1.0, 1.0], 4: [1.0, 1.0]}), ["rms"])
    b1 = out[out["bearing"] == 1].sort_values("timestamp")["rms"].to_numpy()
    np.testing.assert_allclose(b1, [0.0, np.log(3.0)])


def test_reference_excludes_the_bearing_itself():
    out = cross_bearing_log_ratio(frame({1: [8.0], 2: [1.0], 3: [2.0], 4: [4.0]}), ["rms"])
    r = out.set_index("bearing")["rms"]
    assert r[1] == pytest.approx(np.log(8.0) - np.log(2.0))  # median of 1, 2, 4
    assert r[3] == pytest.approx(np.log(2.0) - np.log(4.0))  # median of 8, 1, 4


def test_output_keeps_rows_and_columns():
    df = frame({1: [1.0, 2.0], 2: [1.0, 2.0], 3: [1.0, 2.0]})
    df["kurtosis"] = 3.0
    out = cross_bearing_log_ratio(df, ["rms"])
    assert list(out.columns) == list(df.columns) and len(out) == len(df)
    assert (out["kurtosis"] == 3.0).all()


def test_rejects_missing_bearing_at_a_timestamp():
    df = frame({1: [1.0, 1.0], 2: [1.0, 1.0], 3: [1.0, 1.0]}).iloc[:-1]
    with pytest.raises(ValueError, match="every bearing"):
        cross_bearing_log_ratio(df, ["rms"])


def test_rejects_too_few_bearings():
    with pytest.raises(ValueError, match="at least 3"):
        cross_bearing_log_ratio(frame({1: [1.0], 2: [1.0]}), ["rms"])


def test_rejects_non_positive_values():
    with pytest.raises(ValueError, match="positive"):
        cross_bearing_log_ratio(frame({1: [0.0], 2: [1.0], 3: [1.0]}), ["rms"])
