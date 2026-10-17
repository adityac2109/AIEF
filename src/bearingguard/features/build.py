"""Build per-snapshot feature tables for an IMS test.

Usage:
    python -m bearingguard.features.build --test 1 2 [--set time spectral] [--data-dir DIR]

Reads only files marked "ok" in the validation manifest. Each feature set is
written to its own file under derived/ (one row per snapshot, bearing and
channel), so adding a set never changes an existing file that earlier runs
recorded by hash.
"""

from __future__ import annotations

import argparse
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Callable

import pandas as pd

from bearingguard.config import get_data_dir
from bearingguard.data.ims import extracted_dir, get_spec, list_snapshots, read_snapshot
from bearingguard.data.validate import STATUS_OK
from bearingguard.features.spectral import spectral_features
from bearingguard.features.time_domain import time_domain_features

FEATURE_SETS: dict[str, tuple[Callable, str]] = {
    "time": (time_domain_features, "features_test{}.csv"),
    "spectral": (spectral_features, "features_spectral_test{}.csv"),
}
KEYS = ["test_id", "timestamp", "bearing", "channel", "axis"]

# Each worker process imports numpy/scipy/pandas (~200 MB), so one worker per
# CPU can exhaust memory on a laptop; a few workers already saturate disk I/O.
DEFAULT_WORKERS = min(4, os.cpu_count() or 1)


def manifest_path(data_dir: Path, test_id: int) -> Path:
    return data_dir / "derived" / f"manifest_test{test_id}.csv"


def features_path(data_dir: Path, test_id: int, feature_set: str = "time") -> Path:
    return data_dir / "derived" / FEATURE_SETS[feature_set][1].format(test_id)


def _snapshot_rows(args: tuple[int, str, Path, str, bool]) -> list[dict]:
    test_id, timestamp, path, feature_set, allow_sealed = args
    spec = get_spec(test_id, allow_sealed=allow_sealed)
    extract = FEATURE_SETS[feature_set][0]
    data = read_snapshot(path, spec.n_channels)
    rows = []
    for bearing, cols in spec.bearing_channels.items():
        for axis, col in enumerate(cols):
            rows.append({
                "test_id": test_id,
                "timestamp": timestamp,
                "bearing": bearing,
                "channel": col + 1,  # 1-based, as in the readme
                "axis": axis,        # position within the bearing's channels (test 1 has 2)
                **extract(data[:, col]),
            })
    return rows


def build_features(data_dir: Path, test_id: int, feature_set: str = "time",
                   workers: int | None = None, allow_sealed: bool = False) -> pd.DataFrame:
    get_spec(test_id, allow_sealed=allow_sealed)  # refuses the holdout before any file is touched
    manifest = pd.read_csv(manifest_path(data_dir, test_id))
    ok = manifest[manifest["status"] == STATUS_OK]
    paths = {p.name: p for _, p in list_snapshots(extracted_dir(data_dir, test_id))}
    jobs = [(test_id, ts, paths[name], feature_set, allow_sealed)
            for ts, name in zip(ok["timestamp"], ok["filename"])]

    with ProcessPoolExecutor(max_workers=workers or DEFAULT_WORKERS) as pool:
        rows = [row for chunk in pool.map(_snapshot_rows, jobs, chunksize=16) for row in chunk]

    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df.sort_values(["bearing", "channel", "timestamp"], ignore_index=True)


def load_features(data_dir: Path, test_id: int, sets: tuple[str, ...] = ("time",),
                  allow_sealed: bool = False) -> pd.DataFrame:
    get_spec(test_id, allow_sealed=allow_sealed)
    merged = None
    for s in sets:
        path = features_path(data_dir, test_id, s)
        if not path.exists():
            raise FileNotFoundError(
                f"{path} missing; run python -m bearingguard.features.build --test {test_id} --set {s}")
        df = pd.read_csv(path, parse_dates=["timestamp"])
        merged = df if merged is None else merged.merge(df, on=KEYS, how="inner", validate="1:1")
    return merged


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--test", type=int, nargs="+", required=True)
    parser.add_argument("--set", nargs="+", default=["time"], choices=sorted(FEATURE_SETS))
    parser.add_argument("--data-dir", help="overrides BEARINGGUARD_DATA_DIR")
    parser.add_argument("--workers", type=int, default=None)
    args = parser.parse_args(argv)

    data_dir = get_data_dir(args.data_dir)
    for test_id in args.test:
        for s in args.set:
            df = build_features(data_dir, test_id, s, args.workers)
            out = features_path(data_dir, test_id, s)
            df.to_csv(out, index=False)
            print(f"Test {test_id} [{s}]: {df['timestamp'].nunique()} snapshots, {len(df)} rows -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
