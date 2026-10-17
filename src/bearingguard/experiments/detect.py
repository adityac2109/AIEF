"""Evaluate every candidate detector under one protocol.

Usage:
    python -m bearingguard.experiments.detect configs/protocol_v1.toml [--allow-sealed]

For each test and bearing (one channel per bearing), every method in the
config is run on the same rows with the same boundaries:

    rows [0, n_cal)                    calibration, never scored
      [0, n_cal - n_hold)              fit rows for Isolation Forest
      [n_cal - n_hold, n_cal)          held-out calibration scores for thresholds
    rows [n_cal, end]                  evaluation
      restart windows (if recentering) unscored, counted as blind time

Outputs (runs/<name>/):
    per_bearing.csv   metrics for every method x threshold setting x seed x bearing
    validity.csv      per-snapshot exceedance rates of p-value thresholds vs alpha
    timeline.csv      per-snapshot scores and alarms at each method's primary setting
    metadata.json     commit, versions, input hashes, runtimes
"""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import time
import tomllib
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn

from bearingguard import __version__
from bearingguard.config import get_data_dir
from bearingguard.data.ims import get_spec
from bearingguard.evaluation.alarms import (
    alarm_in_final_window,
    alarm_metrics,
    operating_hours,
    persistent_alarm,
    restart_triggered_episodes,
)
from bearingguard.experiments.threshold_baseline import (
    DIAG_RESTART_GAP_S,
    DIAG_WINDOW_H,
    _git,
    _sha256,
)
from bearingguard.features.build import features_path, load_features
from bearingguard.models.isolation_forest import IsolationForestScorer
from bearingguard.models.recalibration import recenter_features
from bearingguard.models.thresholds import calibration_pvalues, ksigma_exceed, pvalue_exceed
from bearingguard.models.threshold import ZScoreThreshold

FEATURE_FILE_SETS = {"time": ("time",), "time_env": ("time", "spectral")}


def method_outputs(df: pd.DataFrame, method: dict, cfg: dict) -> tuple[list[dict], np.ndarray]:
    """Scores and exceedances for every threshold setting / seed of one method.

    Returns (outputs, scored) where arrays cover all rows of df; calibration
    and restart-window rows are unscored and never exceed.
    """
    feats = cfg["feature_sets"][method["features"]]
    n_cal = cfg["calibration_snapshots"]
    n_fit = n_cal - cfg["calibration_holdout_snapshots"]
    X = df[feats].to_numpy(dtype=np.float64)
    ts = df["timestamp"].to_numpy()

    scored = np.ones(len(X), dtype=bool)
    scored[:n_cal] = False
    if method["recenter"]:
        rc = cfg["recentering"]
        X, window = recenter_features(X, ts, n_cal, rc["snapshots"], rc["restart_gap_s"])
        scored &= ~window

    grid = cfg["grid"]
    outputs = []
    if method["detector"] == "zscore":
        # Per-feature z against all calibration rows; "any feature > k" == max z > k.
        zmax = ZScoreThreshold(k=np.inf).fit(X[:n_cal]).score(X).max(axis=1)
        for k in grid["k_sigma"]:
            outputs.append({"param": "k", "value": k, "seed": -1, "score": zmax,
                            "exceed": (zmax > k) & scored, "pvalues": None})
    elif method["detector"] == "iforest":
        ifc = cfg["isolation_forest"]
        for seed in ifc["seeds"]:
            s = IsolationForestScorer(ifc["n_estimators"], seed).fit(X[:n_fit]).score(X)
            cal = s[n_fit:n_cal]
            norm = (s - cal.mean()) / cal.std(ddof=1)
            if method["threshold"] == "ksigma":
                for k in grid["k_sigma"]:
                    outputs.append({"param": "k", "value": k, "seed": seed, "score": norm,
                                    "exceed": ksigma_exceed(s, cal, k) & scored, "pvalues": None})
            elif method["threshold"] == "pvalue":
                p = calibration_pvalues(s, cal)
                for a in grid["alpha"]:
                    outputs.append({"param": "alpha", "value": a, "seed": seed, "score": norm,
                                    "exceed": pvalue_exceed(s, cal, a) & scored, "pvalues": p})
            else:
                raise ValueError(f"unknown threshold {method['threshold']!r}")
    else:
        raise ValueError(f"unknown detector {method['detector']!r}")
    return outputs, scored


def is_primary(out: dict, cfg: dict) -> bool:
    grid = cfg["grid"]
    primary_value = grid["primary_k"] if out["param"] == "k" else grid["primary_alpha"]
    seed_ok = out["seed"] in (-1, cfg["isolation_forest"]["primary_seed"])
    return bool(np.isclose(out["value"], primary_value) and seed_ok)


def evaluate_bearing(df: pd.DataFrame, info: dict, cfg: dict):
    n_cal = cfg["calibration_snapshots"]
    if len(df) <= n_cal + cfg["persistence_window"]:
        raise ValueError(f"bearing {info} has too few snapshots after calibration")
    ev = slice(n_cal, None)
    ts = df["timestamp"].to_numpy()[ev]
    hours = operating_hours(ts, cfg["max_operating_gap_s"])
    early = hours - hours[0] < (hours[-1] - hours[0]) / 2

    rows, validity, timelines = [], [], []
    for method in cfg["methods"]:
        t0 = time.perf_counter()
        outputs, scored = method_outputs(df, method, cfg)
        runtime = time.perf_counter() - t0
        sc = scored[ev]
        for out in outputs:
            ex = out["exceed"][ev]
            alarm = persistent_alarm(ex, cfg["persistence_required"], cfg["persistence_window"])
            m = alarm_metrics(ts, alarm, cfg["max_operating_gap_s"])
            primary = is_primary(out, cfg)
            rows.append({
                **info, "method": method["name"], "param": out["param"],
                "value": out["value"], "seed": out["seed"], "primary": primary, **m,
                "episodes_per_100h": 100 * m["episodes"] / m["monitored_hours"],
                "detected": alarm_in_final_window(ts, alarm, cfg["max_operating_gap_s"],
                                                  cfg["final_window_h"]),
                "blind_fraction": float(1 - sc.mean()),
                "restart_triggered_episodes": restart_triggered_episodes(
                    ts, alarm, DIAG_RESTART_GAP_S, DIAG_WINDOW_H),
                "runtime_s": runtime / len(outputs),
            })
            if out["pvalues"] is not None:
                near = np.flatnonzero(sc)[: cfg["calibration_holdout_snapshots"]]
                validity.append({
                    **info, "method": method["name"], "alpha": out["value"], "seed": out["seed"],
                    "n_near": len(near),
                    "exceed_rate_near": float(ex[near].mean()),
                    "exceed_rate_early_half": float(ex[early & sc].mean()),
                    "exceed_rate_all": float(ex[sc].mean()),
                })
            if primary:
                timelines.append(pd.DataFrame({
                    **{k: info[k] for k in ("test_id", "bearing")}, "method": method["name"],
                    "timestamp": ts, "score": out["score"][ev], "scored": sc,
                    "exceed": ex, "alarm": alarm,
                }))
    return rows, validity, timelines


def load_test(data_dir: Path, test_id: int, cfg: dict, allow_sealed: bool) -> pd.DataFrame:
    spec = get_spec(test_id, allow_sealed=allow_sealed)
    sets = sorted({s for m in cfg["methods"] for s in FEATURE_FILE_SETS[m["features"]]})
    df = load_features(data_dir, test_id, tuple(sets), allow_sealed=allow_sealed)
    df = df[df["axis"] == cfg["axis"]]
    if cfg.get("restrict_to_documented_end", True) and spec.documented_end is not None:
        df = df[df["timestamp"] <= pd.Timestamp(spec.documented_end)]
    return df


def run(cfg: dict, data_dir: Path, allow_sealed: bool = False):
    rows, validity, timelines = [], [], []
    for test_id in cfg["tests"]:
        spec = get_spec(test_id, allow_sealed=allow_sealed)
        df = load_test(data_dir, test_id, cfg, allow_sealed)
        for bearing, g in df.groupby("bearing"):
            g = g.sort_values("timestamp", ignore_index=True)
            info = {"test_id": test_id, "bearing": int(bearing),
                    "failed": bearing in spec.failures,
                    "failure_mode": spec.failures.get(bearing, ""),
                    "end_time": str(g["timestamp"].iloc[-1])}
            r, v, t = evaluate_bearing(g, info, cfg)
            rows += r
            validity += v
            timelines += t
    return (pd.DataFrame(rows), pd.DataFrame(validity),
            pd.concat(timelines, ignore_index=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("config", type=Path)
    parser.add_argument("--data-dir", help="overrides BEARINGGUARD_DATA_DIR")
    parser.add_argument("--out-root", type=Path, default=Path("runs"))
    parser.add_argument("--allow-sealed", action="store_true",
                        help="permit sealed tests; only the frozen holdout procedure uses this")
    args = parser.parse_args(argv)

    cfg = tomllib.loads(args.config.read_text())
    data_dir = get_data_dir(args.data_dir)
    t0 = time.perf_counter()
    per_bearing, validity, timeline = run(cfg, data_dir, args.allow_sealed)

    out = args.out_root / cfg["name"]
    out.mkdir(parents=True, exist_ok=True)
    per_bearing.to_csv(out / "per_bearing.csv", index=False)
    validity.to_csv(out / "validity.csv", index=False)
    timeline.to_csv(out / "timeline.csv", index=False)
    shutil.copy(args.config, out / "config.toml")
    sets = sorted({s for m in cfg["methods"] for s in FEATURE_FILE_SETS[m["features"]]})
    metadata = {
        "experiment": cfg["name"],
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_commit": _git("rev-parse", "HEAD"),
        "git_dirty": bool(_git("status", "--porcelain")),
        "allow_sealed": args.allow_sealed,
        "package_version": __version__,
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "scikit_learn": sklearn.__version__,
        "input_sha256": {
            f"test{t}/{s}": _sha256(features_path(data_dir, t, s))
            for t in cfg["tests"] for s in sets
        } | {
            f"test{t}/manifest": _sha256(data_dir / "derived" / f"manifest_test{t}.csv")
            for t in cfg["tests"]
        },
        "total_runtime_s": round(time.perf_counter() - t0, 2),
    }
    (out / "metadata.json").write_text(json.dumps(metadata, indent=2))
    print(f"Wrote results to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
