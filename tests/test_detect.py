import numpy as np
import pandas as pd
import pytest

from bearingguard.data.ims import SealedTestError
from bearingguard.experiments import detect
from bearingguard.experiments.threshold_baseline import ANY, run_bearing

FEATS = ["rms", "kurtosis", "crest_factor", "env_bpfo"]

CFG = {
    "tests": [2],
    "axis": 0,
    "calibration_snapshots": 40,
    "calibration_holdout_snapshots": 15,
    "persistence_required": 3,
    "persistence_window": 5,
    "max_operating_gap_s": 3600,
    "final_window_h": 2,
    "recentering": {"restart_gap_s": 8 * 3600, "snapshots": 6},
    "feature_sets": {"time": FEATS[:3], "time_env": FEATS},
    "isolation_forest": {"n_estimators": 50, "seeds": [0, 1], "primary_seed": 0},
    "grid": {"k_sigma": [3.0, 5.0], "alpha": [0.1, 0.0625], "primary_k": 3.0, "primary_alpha": 0.1},
    "methods": [
        {"name": "z_raw", "detector": "zscore", "features": "time", "threshold": "ksigma", "recenter": False},
        {"name": "if_k", "detector": "iforest", "features": "time_env", "threshold": "ksigma", "recenter": True},
        {"name": "if_p", "detector": "iforest", "features": "time_env", "threshold": "pvalue", "recenter": True},
    ],
}
INFO = {"test_id": 2, "bearing": 1, "failed": True, "failure_mode": "outer race", "end_time": ""}


def bearing_frame(n=150, seed=0, degrade_from=None):
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        "test_id": 2, "bearing": 1, "channel": 1, "axis": 0,
        "timestamp": pd.date_range("2004-02-12", periods=n, freq="10min"),
        "rms": rng.normal(0.1, 0.005, n), "kurtosis": rng.normal(3.5, 0.1, n),
        "crest_factor": rng.normal(4.0, 0.1, n), "env_bpfo": rng.normal(5.5, 0.2, n),
    })
    if degrade_from is not None:
        df.loc[degrade_from:, ["rms", "env_bpfo"]] *= 3
    return df


def test_row_count_covers_every_setting_and_seed():
    rows, validity, timelines = detect.evaluate_bearing(bearing_frame(), INFO, CFG)
    # z: 2 k values; if_k: 2 seeds x 2 k; if_p: 2 seeds x 2 alpha
    assert len(rows) == 2 + 4 + 4
    assert len(validity) == 4
    assert {t["method"].iloc[0] for t in timelines} == {"z_raw", "if_k", "if_p"}
    assert sum(r["primary"] for r in rows) == 3


def test_zscore_matches_original_runner():
    df = bearing_frame(degrade_from=120)
    rows, _, _ = detect.evaluate_bearing(df, INFO, CFG)
    new = next(r for r in rows if r["method"] == "z_raw" and r["value"] == 3.0)
    old_cfg = {"calibration_snapshots": 40, "features": FEATS[:3], "persistence_required": 3,
               "persistence_window": 5, "max_operating_gap_s": 3600}
    old = next(r for r in run_bearing(df, old_cfg, 3.0)[0] if r["detector"] == ANY)
    for k in ("episodes", "alarm_fraction", "first_alarm_lead_h", "early_half_episodes"):
        assert new[k] == pytest.approx(old[k], nan_ok=True)


def test_degradation_is_detected_in_final_window():
    rows, _, _ = detect.evaluate_bearing(bearing_frame(degrade_from=130), INFO, CFG)
    primary = {r["method"]: r for r in rows if r["primary"]}
    assert primary["z_raw"]["detected"] and primary["if_p"]["detected"]


def test_iforest_score_saturates_beyond_training_range():
    # Isolation depth bottoms out once a point leaves the training range, so a
    # 50-sigma departure scores barely higher than a 5-sigma one. This bounds
    # what a k-sigma rule on the calibration-score spread can detect.
    from bearingguard.models.isolation_forest import IsolationForestScorer
    X = np.random.default_rng(0).normal(size=(100, 3))
    m = IsolationForestScorer(seed=0).fit(X)
    s5, s50 = m.score(np.full((1, 3), 5.0))[0], m.score(np.full((1, 3), 50.0))[0]
    assert s50 - s5 < 0.05 * s5


def test_future_rows_do_not_change_past_exceedances():
    df = bearing_frame()
    altered = df.copy()
    altered.loc[100:, FEATS] *= 10
    for method in CFG["methods"]:
        a, _ = detect.method_outputs(df, method, CFG)
        b, _ = detect.method_outputs(altered, method, CFG)
        for oa, ob in zip(a, b):
            np.testing.assert_array_equal(oa["exceed"][:100], ob["exceed"][:100])


def test_calibration_and_restart_rows_never_exceed():
    df = bearing_frame()
    df.loc[80:, "timestamp"] += pd.Timedelta(hours=30)  # shutdown before row 80
    df.loc[:, FEATS] *= np.r_[np.ones(40), np.full(110, 50.0)][:, None]  # huge shift after calibration
    outputs, scored = detect.method_outputs(df, CFG["methods"][1], CFG)
    assert not scored[:40].any() and not scored[80:86].any() and scored[86:].all()
    for out in outputs:
        assert not out["exceed"][~scored].any()


def test_sealed_test_refused(tmp_path):
    with pytest.raises(SealedTestError):
        detect.run({**CFG, "tests": [3]}, tmp_path)


def test_unknown_detector_rejected():
    with pytest.raises(ValueError, match="unknown detector"):
        detect.method_outputs(bearing_frame(), {**CFG["methods"][0], "detector": "svm"}, CFG)
