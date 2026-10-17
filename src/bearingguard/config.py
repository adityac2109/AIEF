"""Runtime configuration shared across the package."""

from __future__ import annotations

import os
from pathlib import Path

DATA_DIR_ENV = "BEARINGGUARD_DATA_DIR"
DOTENV = ".env"  # untracked, machine-specific; see .env.example


def read_dotenv(path: Path) -> dict[str, str]:
    """Parse simple KEY=VALUE lines; blank lines and # comments are ignored.

    Deliberately minimal: no variable expansion and no command execution.
    """
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def get_data_dir(override: str | Path | None = None, dotenv: Path | None = None) -> Path:
    """Return the root data directory.

    Precedence: explicit override (--data-dir), then the BEARINGGUARD_DATA_DIR
    environment variable, then a local .env file in the working directory.
    There is deliberately no default inside the repository: the extracted IMS
    data is ~5 GB, and machine-specific paths must not be committed.
    """
    value = override if override is not None else os.environ.get(DATA_DIR_ENV)
    if not value:
        value = read_dotenv(dotenv or Path.cwd() / DOTENV).get(DATA_DIR_ENV)
    if not value:
        raise RuntimeError(
            f"No data directory configured. Set {DATA_DIR_ENV}, pass --data-dir, or copy "
            ".env.example to .env (see data/README.md)."
        )
    return Path(value).expanduser().resolve()
