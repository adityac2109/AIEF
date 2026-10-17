"""Validate every snapshot of an IMS test and write a per-file manifest.

Usage:
    python -m bearingguard.data.validate --test 1 2 [--data-dir DIR]

The manifest (derived/manifest_test{N}.csv under the data directory) records,
for every file, whether it is usable and why not. Downstream code reads only
files marked "ok", so exclusions are explicit and auditable rather than silent.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np

from bearingguard.config import get_data_dir
from bearingguard.data.ims import (
    SnapshotFormatError,
    TestSpec,
    extracted_dir,
    get_spec,
    list_snapshots,
    read_snapshot,
)

# A channel whose RMS falls below this is treated as carrying no vibration
# signal (sensor off or rig stopped during acquisition). Measured on tests 1-2:
# the two dead files at the end of test 2 have channel RMS <= 0.0040, while the
# quietest channel of any running file is 0.0537 (units undocumented), so the
# threshold sits >5x from both. The rule depends only on the file itself, so
# it uses no information from later in the run.
DEAD_RMS_THRESHOLD = 0.01

STATUS_OK = "ok"
STATUS_DEAD = "dead_signal"
STATUS_INVALID = "invalid_format"


@dataclass
class FileRecord:
    timestamp: datetime
    path: Path
    status: str
    reason: str = ""
    channel_rms: list[float] = field(default_factory=list)
    interval_s: float | None = None


def check_file(path: Path, timestamp: datetime, spec: TestSpec,
               dead_threshold: float = DEAD_RMS_THRESHOLD) -> FileRecord:
    try:
        data = read_snapshot(path, spec.n_channels)
    except SnapshotFormatError as exc:
        return FileRecord(timestamp, path, STATUS_INVALID, str(exc))
    rms = np.sqrt(np.mean(data**2, axis=0)).tolist()
    dead = [i + 1 for i, r in enumerate(rms) if r < dead_threshold]
    if dead:
        return FileRecord(timestamp, path, STATUS_DEAD,
                          f"RMS < {dead_threshold} on channel(s) {dead}", rms)
    return FileRecord(timestamp, path, STATUS_OK, "", rms)


def validate_test(data_dir: Path, test_id: int,
                  dead_threshold: float = DEAD_RMS_THRESHOLD,
                  allow_sealed: bool = False) -> list[FileRecord]:
    spec = get_spec(test_id, allow_sealed=allow_sealed)  # refuses the sealed holdout by default
    snapshots = list_snapshots(extracted_dir(data_dir, test_id))
    if not snapshots:
        raise FileNotFoundError(f"No snapshot files under {extracted_dir(data_dir, test_id)}")

    records = []
    prev: datetime | None = None
    for ts, path in snapshots:
        rec = check_file(path, ts, spec, dead_threshold)
        if prev is not None:
            rec.interval_s = (ts - prev).total_seconds()
            if rec.interval_s <= 0:
                # Duplicate timestamps would break temporal ordering downstream.
                rec.status, rec.reason = STATUS_INVALID, "duplicate timestamp"
        prev = ts
        records.append(rec)
    return records


def write_manifest(records: list[FileRecord], spec: TestSpec, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "filename", "status", "reason", "interval_s",
                    *[f"rms_ch{i + 1}" for i in range(spec.n_channels)]])
        for r in records:
            rms = [f"{v:.5f}" for v in r.channel_rms] or [""] * spec.n_channels
            w.writerow([r.timestamp.isoformat(), r.path.name, r.status, r.reason,
                        "" if r.interval_s is None else f"{r.interval_s:.0f}", *rms])


def summarize(records: list[FileRecord], spec: TestSpec) -> str:
    statuses = Counter(r.status for r in records)
    intervals = Counter(int(r.interval_s) for r in records if r.interval_s is not None)
    gaps = sorted((r for r in records if r.interval_s and r.interval_s > 3600),
                  key=lambda r: -r.interval_s)
    lines = [
        f"Test {spec.test_id}: {len(records)} files (readme: {spec.expected_files})",
        f"  span: {records[0].timestamp} -> {records[-1].timestamp}",
        f"  status: {dict(statuses)}",
        f"  most common intervals (s): {intervals.most_common(4)}",
        f"  gaps > 1 h: {len(gaps)}"
        + "".join(f"\n    {g.interval_s / 3600:.1f} h before {g.timestamp}" for g in gaps[:5]),
    ]
    for r in records:
        if r.status != STATUS_OK:
            lines.append(f"  {r.status}: {r.path.name} - {r.reason}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--test", type=int, nargs="+", required=True)
    parser.add_argument("--data-dir", help="overrides BEARINGGUARD_DATA_DIR")
    args = parser.parse_args(argv)

    data_dir = get_data_dir(args.data_dir)
    for test_id in args.test:
        spec = get_spec(test_id)
        records = validate_test(data_dir, test_id)
        out = data_dir / "derived" / f"manifest_test{test_id}.csv"
        write_manifest(records, spec, out)
        print(summarize(records, spec))
        print(f"  manifest: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
