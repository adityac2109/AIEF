# BearingGuard

How much early warning can vibration-based anomaly detection give before a
bearing fails, at what false-alarm cost? And does an uncertainty-calibrated
alarm threshold improve that trade-off over a fixed one? BearingGuard studies
these questions on the NASA IMS run-to-failure bearing data, using strict
held-out evaluation.

## Status

| Done | Next |
|---|---|
| Data download, checksum, validation and manifest | Frequency-domain features (bearing defect bands) |
| Time-domain features (RMS, kurtosis, crest factor, …) | Isolation Forest baseline |
| Per-bearing k-σ threshold baseline with persistence alarms | Conformal / uncertainty-aware alarm thresholds |
| Calibration study: restart re-centering vs cross-bearing normalization | Final evaluation on sealed test 3 |

All results so far are on development tests 1 and 2 and use proxy labels.
See [docs/experiment_protocol.md](docs/experiment_protocol.md) for what the
metrics can and cannot show.

## Setup

Requires Python 3.11+.

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows; use .venv/bin/activate elsewhere
pip install -e ".[dev]"
pytest
```

See [data/README.md](data/README.md) to obtain and validate the dataset, and
[docs/experiment_protocol.md](docs/experiment_protocol.md#reproduction) to
reproduce the experiments.

## Layout

```
configs/                     experiment configs (one file per run)
docs/                        protocol and results
src/bearingguard/
  data/                      download, parsing, validation, test 3 seal
  features/                  per-snapshot condition indicators
  preprocessing/             cross-bearing normalization
  models/                    k-sigma threshold, restart re-centering
  evaluation/                persistence alarms and alarm metrics
  experiments/               experiment runner and comparison report
tests/
```

## Evaluation discipline

- IMS test 3 is sealed as the final holdout and cannot be loaded by development code.
- Detectors are calibrated per bearing on early data only. Tests check that
  changing later data leaves earlier scores and alarms unchanged.
- Files that fail validation are recorded in a manifest with the reason. They
  are never dropped silently.
- Experiment parameters are fixed in configs before results are seen, and each
  run records its Git commit and input hashes.
