"""Shared helpers that build tiny IMS-format fixtures in a temp directory.

These are format fixtures for exercising the parser and validator, not
stand-ins for real measurements.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from bearingguard.data.ims import SAMPLES_PER_FILE


def write_snapshot(path: Path, data: np.ndarray) -> None:
    # Mirror the real files: tab-separated, CRLF line endings, 3 decimals.
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        for row in data:
            f.write("\t".join(f"{v:.3f}" for v in row) + "\r\n")


@pytest.fixture
def make_snapshot():
    rng = np.random.default_rng(0)

    def _make(path: Path, n_channels: int = 4, scale: float = 0.1,
              n_rows: int = SAMPLES_PER_FILE) -> Path:
        write_snapshot(path, rng.normal(0.0, scale, size=(n_rows, n_channels)))
        return path

    return _make
