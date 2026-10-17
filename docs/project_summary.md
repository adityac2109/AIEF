# Project summary

## One paragraph

BearingGuard is a reproducible evaluation of vibration-based anomaly detection
for rolling-element bearings on the NASA IMS run-to-failure dataset. It builds an
MD5-verified ingestion and validation pipeline, time-domain and
envelope-spectrum (BPFO/BPFI/BSF) features, per-bearing z-score and Isolation
Forest detectors with restart re-centering, and k·σ and calibration p-value alarm
thresholds. Every method is evaluated under one leakage-tested protocol, and a
sealed holdout test was opened once, after the protocol was frozen and Git-tagged.
The main findings are negative or mixed. No detector dominated. Rig restarts
caused most of a naive baseline's apparent lead time. Calibrated p-value
thresholds exceeded their nominal false-alarm rate 3.6–5.7× over whole runs. On
the holdout, the documented failure left no feature-level trace before its
documented end time.

## Resume bullets

- Built BearingGuard, a Python pipeline (NumPy, SciPy, pandas, scikit-learn) for
  bearing degradation detection on NASA IMS vibration data (3 run-to-failure
  tests, 9,461 usable one-second snapshots at 20 kHz), with 130 automated tests
  covering parsing, leakage prevention, holdout sealing and publication hygiene.
- Designed a leakage-safe protocol: per-bearing calibration, causal scoring
  checked by tests, and a sealed holdout that could only be opened from a clean
  checkout matching a frozen Git tag. Evaluated 7 detector configurations
  (z-score and Isolation Forest × time/envelope features × k·σ/p-value
  thresholds) with full sensitivity grids and 5 seeds.
- Found that rig restarts shifted vibration on all bearings at once (+14% to
  +22% RMS), inflating a baseline's lead times past 300 h. Restart re-centering
  cut restart-triggered alarms from 14 to 4 and exposed a masking failure case.
- Showed empirically that calibration p-value thresholds lose their nominal
  false-alarm rate on drifting data (3.6–5.7× α over whole runs), and that the
  holdout's documented failure time precedes any measurable degradation. Both
  were reported as negative results.

## What not to claim

- No industrial validation, financial savings or remaining-useful-life estimates.
- No statistical significance: there are four documented failures.
- The p-value thresholds are not "conformal guarantees" on these data.
