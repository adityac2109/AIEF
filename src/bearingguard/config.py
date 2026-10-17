"""Runtime configuration shared across the package."""

from __future__ import annotations

import os
from pathlib import Path

DATA_DIR_ENV = "BEARINGGUARD_DATA_DIR"


def get_data_dir(override: str | Path | None = None) -> Path:
    """Return the root data directory.

    There is deliberately no default inside the repository: the extracted IMS
    data is ~5 GB of ASCII, and the repo may live in a synced folder.
    """
    value = override if override is not None else os.environ.get(DATA_DIR_ENV)
    if not value:
        raise RuntimeError(
            f"No data directory configured. Set {DATA_DIR_ENV} or pass --data-dir "
            "(see data/README.md)."
        )
    return Path(value).expanduser().resolve()
