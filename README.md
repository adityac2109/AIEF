# BearingGuard

How much early warning can vibration-based anomaly detection give before a
bearing fails, at what false-alarm cost? And does an uncertainty-calibrated
alarm threshold improve that trade-off over a fixed one? BearingGuard studies
these questions on the NASA IMS run-to-failure bearing data, using strict
held-out evaluation.

## Status

Milestone 1 (data ingestion and validation) is in progress. No models or
results exist yet.

## Setup

Requires Python 3.11+.

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows; use .venv/bin/activate elsewhere
pip install -e ".[dev]"
pytest
```

See [data/README.md](data/README.md) to obtain and validate the dataset.

## Layout

```
src/bearingguard/
  config.py          data-directory configuration
  data/ims.py        dataset facts from the readme, snapshot parsing, holdout seal
  data/download.py   download, checksum, extraction
  data/validate.py   per-file integrity checks and manifest
tests/
```

## Evaluation discipline

- IMS test 3 is sealed as the final holdout and cannot be loaded by development code.
- Splits are made by whole test and bearing, never by randomly mixing snapshots
  from the same recording.
- Files that fail validation are recorded in a manifest with the reason. They
  are never dropped silently.
