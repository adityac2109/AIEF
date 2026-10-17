"""Facts about the IMS bearing dataset and low-level snapshot parsing.

Everything in TESTS is transcribed from "Readme Document for IMS Bearing
Data.pdf" shipped inside IMS.zip. Nothing here is inferred from the signals.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np

SAMPLING_RATE_HZ = 20_000
SAMPLES_PER_FILE = 20_480
SHAFT_SPEED_RPM = 2000

# Snapshot files are named by acquisition time, e.g. "2004.02.12.10.32.39".
_FILENAME_RE = re.compile(r"^\d{4}\.\d{2}\.\d{2}\.\d{2}\.\d{2}\.\d{2}$")
_FILENAME_FMT = "%Y.%m.%d.%H.%M.%S"


@dataclass(frozen=True)
class TestSpec:
    test_id: int
    archive: str
    expected_files: int
    n_channels: int
    # bearing number -> 0-based column indices in the snapshot file
    bearing_channels: dict[int, tuple[int, ...]]
    # bearing number -> failure mode documented at end of test
    failures: dict[int, str]
    # Last recording time stated in the readme. Test 3's archive continues
    # beyond it; see data/README.md and docs/holdout_protocol.md.
    documented_end: datetime | None = None
    # Sealed tests are the final holdout; see load guards below.
    sealed: bool = False

    __test__ = False  # stop pytest from collecting this as a test class


TESTS: dict[int, TestSpec] = {
    1: TestSpec(
        test_id=1,
        archive="1st_test.rar",
        expected_files=2156,
        n_channels=8,
        bearing_channels={1: (0, 1), 2: (2, 3), 3: (4, 5), 4: (6, 7)},
        failures={3: "inner race", 4: "roller element"},
        documented_end=datetime(2003, 11, 25, 23, 39, 56),
    ),
    2: TestSpec(
        test_id=2,
        archive="2nd_test.rar",
        expected_files=984,
        n_channels=4,
        bearing_channels={1: (0,), 2: (1,), 3: (2,), 4: (3,)},
        failures={1: "outer race"},
        documented_end=datetime(2004, 2, 19, 6, 22, 39),
    ),
    3: TestSpec(
        test_id=3,
        archive="3rd_test.rar",
        expected_files=4448,
        n_channels=4,
        bearing_channels={1: (0,), 2: (1,), 3: (2,), 4: (3,)},
        failures={3: "outer race"},
        documented_end=datetime(2004, 4, 4, 19, 1, 57),
        sealed=True,
    ),
}


class SealedTestError(PermissionError):
    """Raised when sealed holdout data is requested without explicit opt-in."""


class SnapshotFormatError(ValueError):
    """Raised when a snapshot file does not match the documented format."""


def get_spec(test_id: int, *, allow_sealed: bool = False) -> TestSpec:
    """Look up a test, refusing sealed tests unless explicitly unsealed.

    Every code path that touches signal data goes through this check, so
    development code cannot read the holdout by accident. Only the frozen
    final-evaluation step should pass allow_sealed=True.
    """
    try:
        spec = TESTS[test_id]
    except KeyError:
        raise ValueError(f"Unknown IMS test {test_id}; expected one of {sorted(TESTS)}") from None
    if spec.sealed and not allow_sealed:
        raise SealedTestError(
            f"Test {test_id} is the sealed final holdout. It may only be read by the "
            "final evaluation after the protocol is frozen (allow_sealed=True)."
        )
    return spec


def extracted_dir(data_dir: Path, test_id: int) -> Path:
    """Directory that the test's archive is extracted into."""
    return data_dir / "raw" / f"test{test_id}"


def parse_timestamp(name: str) -> datetime:
    if not _FILENAME_RE.match(name):
        raise SnapshotFormatError(f"Not an IMS snapshot filename: {name!r}")
    return datetime.strptime(name, _FILENAME_FMT)


def list_snapshots(root: Path) -> list[tuple[datetime, Path]]:
    """Find snapshot files under root, sorted by acquisition time.

    Searches recursively because the archives do not share one internal layout.
    Files that do not look like snapshots (e.g. archive metadata) are ignored.
    """
    found = [
        (parse_timestamp(p.name), p)
        for p in root.rglob("*")
        if p.is_file() and _FILENAME_RE.match(p.name)
    ]
    found.sort(key=lambda item: item[0])
    return found


def read_snapshot(path: Path, n_channels: int) -> np.ndarray:
    """Read one snapshot as a (SAMPLES_PER_FILE, n_channels) float64 array.

    Raises SnapshotFormatError instead of returning a partially valid array, so
    callers must decide explicitly how to treat a bad file.
    """
    try:
        # Whitespace delimiter covers the tab-separated, CRLF-terminated files.
        data = np.loadtxt(path, dtype=np.float64, ndmin=2)
    except ValueError as exc:
        raise SnapshotFormatError(f"{path.name}: unparseable values ({exc})") from exc
    if data.shape != (SAMPLES_PER_FILE, n_channels):
        raise SnapshotFormatError(
            f"{path.name}: shape {data.shape}, expected ({SAMPLES_PER_FILE}, {n_channels})"
        )
    if not np.isfinite(data).all():
        raise SnapshotFormatError(f"{path.name}: contains non-finite values")
    return data
