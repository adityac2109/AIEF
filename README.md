# BearingGuard

**Leakage-safe evaluation of vibration-based anomaly detection for bearing
run-to-failure data, with a pre-registered holdout.**

Unexpected bearing failures stop rotating machinery. BearingGuard asks:
*how reliably can vibration-based detectors flag bearing degradation under
realistic evaluation, and does a calibrated (uncertainty-aware) alarm threshold
improve the trade-off between missed failures and false alarms?* It answers on
the NASA IMS bearing data with per-bearing calibration, explicit handling of rig
shutdowns, and a sealed test set that was opened once, after the protocol was
frozen and tagged.

> This is anomaly detection. Scores are not failure probabilities or
> remaining-useful-life estimates, and nothing here has been validated on
> industrial equipment.

## Key findings

All results are case studies (4 documented failures across 3 tests). No
statistical significance is claimed.

**Development (tests 1–2)** — [detector_comparison.md](docs/results/detector_comparison.md)

- **No method dominates (H1).** The detector with the least non-failed time in
  alarm (Isolation Forest on time + envelope features: 3.9%) also raises 27
  early-half alarm episodes on failed bearing T1B4. The detector with the fewest
  early alarms misses a failure.
- **Rig restarts dominate a naive baseline.** After a 148 h shutdown, RMS on all
  four bearings jumped 14–22% at once. That made the baseline's 300 h+ "lead
  times" artifacts. Re-centering after shutdowns of 8 h or more cut
  restart-triggered alarms from 14 to 4, but re-centering after every 1 h gap
  left the RMS detector silent on a failed bearing ([calibration_study.md](docs/results/calibration_study.md)).
- **Envelope-spectrum features match 2 of 3 documented defects.** The BPFI band
  rises on the inner-race failure and the BPFO band on the outer-race failure.
  For the roller failure the BSF band stays flat.
- **Calibrated p-value thresholds do not keep their promise (H3).** Near the
  calibration window the observed false-exceedance rate is close to α. Over a
  whole run it reaches 3.6–5.7× α (at α = 0.05), because drift and restarts break
  exchangeability. These are reported as calibration-quantile thresholds, not as
  conformal guarantees.

**Holdout (test 3, evaluated once)** — [holdout_results.md](docs/results/holdout_results.md)

- **Within the readme's documented range, no method meaningfully detects the
  failure.** The features show no degradation of bearing 3 before the documented
  end time (RMS z = 0.4 against calibration).
- The archive holds 13 more days than documented. In the last ~60 operating hours
  all four bearings degrade together. Most detectors then alarm about 59 h before
  the end of the archive, but also on the non-failed bearings, so detection is
  not bearing-specific.

## How it works

```
IMS.zip ─► download (MD5) ─► validate (manifest: ok / dead / invalid) ─► features
                                                                   │  time: RMS, kurtosis, crest factor
                                                                   │  spectral: envelope SNR at BPFO/BPFI/BSF
                                                                   ▼
        per bearing: calibration (first 144 snapshots) ─► restart re-centering ─► detector
                     z-score | Isolation Forest   ×   k·σ | calibration p-value
                                                                   ▼
             3-of-5 persistence alarm ─► metrics (lead time, detected, false alarms/100 h,
                                         time in alarm, blind time, restart-triggered alarms)
                                                                   ▼
                                        tables + figures (reporting) ─► docs/results/
```

- **No leakage by construction.** Each bearing is calibrated only on its own early
  data. Every score uses only past calibration rows and the current snapshot.
  Tests change future data and assert that past alarms do not move.
- **Sealed holdout.** Test 3 could not be read by development code
  (`SealedTestError`). The holdout runner refused to start unless the tree was
  clean and code and configs matched the `protocol-v1-frozen` tag.
- **Proxy labels, stated plainly.** IMS documents only which bearings had failed at
  the end of each test. "Lead time", "detected" and "false alarm" are defined in
  [experiment_protocol.md](docs/experiment_protocol.md) with their caveats.

## Repository layout

```
configs/                    one TOML per experiment; protocol_v1.toml = frozen candidate set
data/README.md              dataset source, license, download, observed quirks
docs/
  experiment_protocol.md    task, proxy labels, splits, metrics, reproduction
  holdout_protocol.md       frozen holdout procedure and test 3 range decision
  report.md                 full project report
  results/                  generated tables and figures, plus written analyses
src/bearingguard/
  data/                     download, parsing, validation, test 3 seal
  features/                 time-domain, envelope-spectrum and bearing kinematics
  preprocessing/            cross-bearing normalization (calibration study)
  models/                   z-score, Isolation Forest, restart re-centering, thresholds
  evaluation/               persistence alarms and alarm metrics
  experiments/              threshold study, unified protocol runner, holdout runner
  reporting/                tables and figures from run outputs
tests/                      103 tests (parsing, features, leakage, seal, metrics, reports)
```

## Setup (Windows, PowerShell)

Requires Python 3.11+ (results were produced with 3.12.13).

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-lock.txt   # exact tested versions
pip install -e ".[dev]"
pytest                                 # 103 tests, about 1 minute
```

On macOS or Linux use `python3 -m venv .venv` and `source .venv/bin/activate`.

## Reproduce the results

```powershell
$env:BEARINGGUARD_DATA_DIR = "D:\data\ims"     # any folder outside the repo, ~7 GB free

python -m bearingguard.data.download            # 1.06 GB, MD5-checked, extracts tests 1-3
python -m bearingguard.data.validate --test 1 2
python -m bearingguard.features.build --test 1 2 --set time spectral

# development comparison (tests 1-2), ~3 min, then tables and figures
python -m bearingguard.experiments.detect configs/protocol_v1.toml
python -m bearingguard.reporting.report runs/protocol_v1_dev --out docs/results/protocol_v1_dev
```

The original baseline and calibration study commands are in
[experiment_protocol.md](docs/experiment_protocol.md#reproduction). The holdout
command (`python -m bearingguard.experiments.holdout --tag protocol-v1-frozen`)
only runs on a checkout identical to the tag. Its recorded outputs are in
`docs/results/holdout_v1_*`.

Every run writes `metadata.json` with the Git commit, whether the tree was clean,
library versions and SHA-256 hashes of its inputs.

## Dataset

NASA IMS Bearings dataset, generated by the NSF I/UCR Center for Intelligent
Maintenance Systems (University of Cincinnati) with support from Rexnord Corp.,
distributed by the NASA Prognostics Center of Excellence
([data.nasa.gov/dataset/ims-bearings](https://data.nasa.gov/dataset/ims-bearings),
U.S. Government Works). Reference: H. Qiu, J. Lee, J. Lin, "Wavelet filter-based
weak signature detection method and its application on roller bearing
prognostics," *Journal of Sound and Vibration* 289 (2006) 1066–1090.
The raw data is not redistributed here; see [data/README.md](data/README.md).

## Limitations

- 4 documented failures (3 in development, 1 in the holdout). Results are case
  studies and do not generalize to other machines or operating conditions.
- No fault-onset labels. All detection metrics rely on end-of-test labels, and
  test 3's documented failure time does not match its recorded vibration.
- One rig, one speed and load, one channel per bearing, a fixed envelope band and
  one calibration length.
- Not examined: remaining-useful-life prediction, deep learning (not justified
  by 4 failures), a dashboard or API (the research pipeline was the priority).

Full discussion: [docs/report.md](docs/report.md).
