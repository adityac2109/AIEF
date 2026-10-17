"""Run the per-bearing k-sigma threshold baseline.

Usage:
    python -m bearingguard.experiments.threshold_baseline configs/threshold_baseline.toml

Task: for each bearing, raise alarms on snapshots whose condition indicators
depart from that bearing's own early-life calibration window. No model is
trained across bearings or tests, so no information moves between them.

Writes to runs/<name>/: per_bearing.csv (metrics), sensitivity.csv (k grid),
timeline.csv (per-snapshot scores and alarms), metadata.json, config.toml.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import tomllib
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from bearingguard import __version__
from bearingguard.config import get_data_dir
from bearingguard.data.ims import get_spec
from bearingguard.evaluation.alarms import alarm_metrics, persistent_alarm
from bearingguard.features.build import features_path, load_features
from bearingguard.models.threshold import ZScoreThreshold

ANY = "any"  # detector that alarms when any configured feature exceeds


def run_bearing(df: pd.DataFrame, cfg: dict, k: float) -> tuple[list[dict], pd.DataFrame]:
    """Evaluate every detector on one bearing's time-ordered feature rows."""
    n_cal = cfg["calibration_snapshots"]
    if len(df) <= n_cal:
        raise ValueError("not enough snapshots after calibration")
    feats = cfg["features"]
    calib, ev = df.iloc[:n_cal], df.iloc[n_cal:]

    model = ZScoreThreshold(k).fit(calib[feats].to_numpy())
    z = model.score(ev[feats].to_numpy())
    exceed = {f: z[:, i] > k for i, f in enumerate(feats)}
    exceed[ANY] = np.any(z > k, axis=1)

    ts = ev["timestamp"].to_numpy()
    timeline = ev[["test_id", "timestamp", "bearing", "channel"]].copy()
    timeline[[f"z_{f}" for f in feats]] = z
    results = []
    for det, ex in exceed.items():
        alarm = persistent_alarm(ex, cfg["persistence_required"], cfg["persistence_window"])
        timeline[f"alarm_{det}"] = alarm
        results.append({"detector": det, **alarm_metrics(ts, alarm, cfg["max_operating_gap_s"])})
    return results, timeline


def run(cfg: dict, data_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows, sens, timelines = [], [], []
    for test_id in cfg["tests"]:
        spec = get_spec(test_id)  # refuses the sealed holdout
        feats = load_features(data_dir, test_id)
        feats = feats[feats["axis"] == cfg["axis"]]
        for bearing, df in feats.groupby("bearing"):
            df = df.sort_values("timestamp", ignore_index=True)
            info = {
                "test_id": test_id,
                "bearing": bearing,
                "channel": int(df["channel"].iloc[0]),
                "failed": bearing in spec.failures,
                "failure_mode": spec.failures.get(bearing, ""),
            }
            for k in cfg["sensitivity_k"]:
                res, tl = run_bearing(df, cfg, k)
                for r in res:
                    sens.append({**info, "k_sigma": k, **r})
                if k == cfg["k_sigma"]:
                    rows += [{**info, **r} for r in res]
                    timelines.append(tl)
    return pd.DataFrame(rows), pd.DataFrame(sens), pd.concat(timelines, ignore_index=True)


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("config", type=Path)
    parser.add_argument("--data-dir", help="overrides BEARINGGUARD_DATA_DIR")
    parser.add_argument("--out-root", type=Path, default=Path("runs"))
    args = parser.parse_args(argv)

    cfg = tomllib.loads(args.config.read_text())
    if cfg["k_sigma"] not in cfg["sensitivity_k"]:
        raise ValueError("k_sigma must be one of sensitivity_k")
    data_dir = get_data_dir(args.data_dir)
    per_bearing, sensitivity, timeline = run(cfg, data_dir)

    out = args.out_root / cfg["name"]
    out.mkdir(parents=True, exist_ok=True)
    per_bearing.to_csv(out / "per_bearing.csv", index=False)
    sensitivity.to_csv(out / "sensitivity.csv", index=False)
    timeline.to_csv(out / "timeline.csv", index=False)
    shutil.copy(args.config, out / "config.toml")
    metadata = {
        "experiment": cfg["name"],
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_commit": _git("rev-parse", "HEAD"),
        "git_dirty": bool(_git("status", "--porcelain")),
        "package_version": __version__,
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "feature_files_sha256": {
            str(t): _sha256(features_path(data_dir, t)) for t in cfg["tests"]
        },
        "randomness": "none (deterministic)",
    }
    (out / "metadata.json").write_text(json.dumps(metadata, indent=2))
    print(f"Wrote results to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
