"""Build the per-snapshot feature table for an IMS test.

Usage:
    python -m bearingguard.features.build --test 1 2 [--data-dir DIR]

Reads only files marked "ok" in the validation manifest and writes
derived/features_test{N}.csv: one row per (snapshot, bearing, channel).
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd

from bearingguard.config import get_data_dir
from bearingguard.data.ims import extracted_dir, get_spec, list_snapshots, read_snapshot
from bearingguard.data.validate import STATUS_OK
from bearingguard.features.time_domain import time_domain_features


def manifest_path(data_dir: Path, test_id: int) -> Path:
    return data_dir / "derived" / f"manifest_test{test_id}.csv"


def features_path(data_dir: Path, test_id: int) -> Path:
    return data_dir / "derived" / f"features_test{test_id}.csv"


def _snapshot_rows(args: tuple[int, str, Path]) -> list[dict]:
    test_id, timestamp, path = args
    spec = get_spec(test_id)
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
                **time_domain_features(data[:, col]),
            })
    return rows


def build_features(data_dir: Path, test_id: int, workers: int | None = None) -> pd.DataFrame:
    get_spec(test_id)  # refuses the sealed holdout before any file is touched
    manifest = pd.read_csv(manifest_path(data_dir, test_id))
    ok = manifest[manifest["status"] == STATUS_OK]
    paths = {p.name: p for _, p in list_snapshots(extracted_dir(data_dir, test_id))}
    jobs = [(test_id, ts, paths[name]) for ts, name in zip(ok["timestamp"], ok["filename"])]

    with ProcessPoolExecutor(max_workers=workers) as pool:
        rows = [row for chunk in pool.map(_snapshot_rows, jobs, chunksize=16) for row in chunk]

    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df.sort_values(["bearing", "channel", "timestamp"], ignore_index=True)


def load_features(data_dir: Path, test_id: int) -> pd.DataFrame:
    get_spec(test_id)
    path = features_path(data_dir, test_id)
    if not path.exists():
        raise FileNotFoundError(f"{path} missing; run python -m bearingguard.features.build --test {test_id}")
    return pd.read_csv(path, parse_dates=["timestamp"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--test", type=int, nargs="+", required=True)
    parser.add_argument("--data-dir", help="overrides BEARINGGUARD_DATA_DIR")
    parser.add_argument("--workers", type=int, default=None)
    args = parser.parse_args(argv)

    data_dir = get_data_dir(args.data_dir)
    for test_id in args.test:
        df = build_features(data_dir, test_id, args.workers)
        out = features_path(data_dir, test_id)
        df.to_csv(out, index=False)
        print(f"Test {test_id}: {df['timestamp'].nunique()} snapshots, {len(df)} rows -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
