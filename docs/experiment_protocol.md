# Experiment protocol

This protocol applies to every development experiment on IMS tests 1 and 2.
It is fixed in code and configs; changes to it are recorded in Git history.

## Task

**Per-bearing alarm decision.** For each bearing, at each 1 s snapshot, decide
whether to raise a maintenance alarm. Detectors are unsupervised: each is
calibrated on the bearing's own early life and flags departures from it.

This is anomaly detection. It does **not** estimate a failure probability or a
remaining useful life, and its scores should not be read as either.

## Data

| | Test 1 | Test 2 |
|---|---|---|
| Usable snapshots | 2,156 of 2,156 | 982 of 984 (2 dead-signal files excluded by validation) |
| Bearings that failed (readme) | B3 inner race, B4 roller element | B1 outer race |
| Bearings that did not fail | B1, B2 | B2, B3, B4 |
| Channel used per bearing | first of the pair (ch 1, 3, 5, 7) | the single channel |

Test 3 was sealed during all development described here (see `data/README.md`).
It was later used once, as the holdout ([holdout_protocol.md](holdout_protocol.md)).

## Labels: proxies only

IMS documents only which bearings had failed **at the end** of each test.
There is no fault-onset time, so per-snapshot ground truth does not exist.
Metrics are therefore defined on alarms with these proxies:

- **Failed bearing:** an alarm counts as a warning. *Lead time* is the operating
  time from the first alarm to the last usable snapshot of the test.
- **Non-failed bearing:** every alarm counts as a false alarm. This is an upper
  bound on true false alarms. These bearings were also beyond their design life,
  and vibration from a failing bearing reaches the other sensors on the shared
  shaft.
- **Early half:** alarms that start in the first half of a bearing's monitored
  time, when damage is least likely. A high count on a failed bearing means its
  "lead time" may come from noise or rig artifacts rather than early detection.

None of these can separate a genuinely early detection from a false alarm on a
failed bearing; that ambiguity is a property of the dataset.

## Split and leakage control

- No model is fitted across bearings or tests. Each bearing's detector sees only
  that bearing's data, so there is no train/test split across tests to leak through.
- Calibration uses the first `calibration_snapshots` (144) usable snapshots of each
  bearing. These are never scored.
- Every score at time t uses only calibration data from before t and the snapshot
  at t (plus, for cross-bearing normalization, other bearings' snapshots at the
  same t). The tests in `tests/test_threshold_baseline.py`,
  `tests/test_recalibration.py` and `tests/test_alarms.py` check that changing
  later data leaves earlier scores and alarms unchanged.
- All parameters (k, persistence, calibration length, restart rules) are fixed
  in configs before results are seen. The k grid {3, 4, 5, 6} is reported in
  full and not used to pick a best value.
- Development experiments may compare methods on tests 1 and 2. The method
  carried to the final evaluation is frozen before test 3 is unsealed.

## Detector

- Features per snapshot: RMS, kurtosis (Pearson, Gaussian = 3), crest factor
  (`bearingguard.features.time_domain`).
- Score: one-sided z-score against the calibration mean and standard deviation.
  A snapshot *exceeds* when z > k.
- Detectors: each feature alone, and `any` (exceeds when any feature does).
- Alarm: at least 3 exceedances among the last 5 snapshots (causal).

## Calibration variants

| Variant | Config | Change from the baseline |
|---|---|---|
| Baseline | `configs/threshold_baseline.toml` | none |
| Restart re-centering | `configs/calibration_study/restart_recenter_{1h,8h,24h}.toml` | After a shutdown ≥ the gap threshold, the next 18 snapshots re-estimate the mean and are not scored. σ stays from the initial calibration. 8 h is the primary setting. |
| Cross-bearing normalization | `configs/calibration_study/cross_bearing.toml` | Features are replaced by `log f_b − median_{j≠b} log f_j` at each snapshot before calibration. |

## Metrics

Per bearing and detector (`runs/<name>/per_bearing.csv`):

| Metric | Meaning |
|---|---|
| `first_alarm_lead_h` | Operating hours from the first alarm to the end of the test |
| `episodes`, `episodes_per_day` | Alarm onsets, in total and per monitored day |
| `alarm_fraction` | Share of evaluated snapshots in alarm. Reported because a detector stuck in alarm has only one episode |
| `early_half_episodes` | Episodes starting in the first half of monitored time |
| `restart_triggered_episodes` | Episodes starting ≤ 6 h after a shutdown ≥ 8 h, defined the same way for every method |
| `blind_fraction` | Share of evaluated snapshots the method does not score |

Operating time excludes gaps over 1 h between snapshots (rig switched off).

## Protocol v1: candidate methods

`configs/protocol_v1.toml`, run by `bearingguard.experiments.detect`, extends
the setup above to every candidate method under one set of boundaries.

| Rows of each bearing | Use |
|---|---|
| 1–96 | Isolation Forest fit rows; part of z-score calibration |
| 97–144 | held-out calibration scores for Isolation Forest thresholds; part of z-score calibration |
| 145 – end | evaluation; restart windows (18 snapshots after a shutdown ≥ 8 h) unscored |

- **Features.** Time-domain features as above, plus envelope SNR at BPFO, BPFI and
  BSF (`bearingguard.features.spectral`). The defect frequencies are computed
  from the ZA-2115 geometry; the band and tolerances are fixed in advance.
  Units cancel in every spectral feature.
- **Restart re-centering** is applied to the features, so every detector sees
  the same adjusted inputs.
- **Isolation Forest.** 200 trees, standardized on the fit rows, 5 seeds.
- **Thresholds.** k·σ of the held-out calibration scores, or an empirical
  p-value against them (exceed when p ≤ α). The p-value is valid only under
  exchangeability; its observed rate is measured, not assumed.
- **Extra metrics.** `detected` (failed bearing in alarm within its last 24
  operating hours), `episodes_per_100h`, and `validity.csv` (per-snapshot
  exceedance rate vs α near calibration, in the first half, and over the whole run).
- **Holdout.** [holdout_protocol.md](holdout_protocol.md).

## Reproduction

```bash
export BEARINGGUARD_DATA_DIR=<path-to-ims-data>   # PowerShell: $env:BEARINGGUARD_DATA_DIR = "<path-to-ims-data>"
python -m bearingguard.data.download
python -m bearingguard.data.validate --test 1 2
python -m bearingguard.features.build --test 1 2 --set time spectral
python -m bearingguard.experiments.threshold_baseline configs/threshold_baseline.toml
for c in configs/calibration_study/*.toml; do
  python -m bearingguard.experiments.threshold_baseline "$c"
done
python -m bearingguard.experiments.compare runs/threshold_baseline_v1 \
  runs/calib_restart_recenter_8h runs/calib_restart_recenter_1h \
  runs/calib_restart_recenter_24h runs/calib_cross_bearing --k 3 \
  --out docs/results/calibration_study_tables.md
python -m bearingguard.experiments.detect configs/protocol_v1.toml
python -m bearingguard.reporting.report runs/protocol_v1_dev --out docs/results/protocol_v1_dev
```

Each run writes `metadata.json` with the Git commit, whether the tree was clean,
library versions and SHA-256 hashes of the feature files it read. All
detectors are deterministic, so random seeds do not apply.
