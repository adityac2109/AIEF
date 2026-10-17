# Holdout protocol (v1)

This document was committed **before** any IMS test 3 vibration contents were
read. The commit is tagged `protocol-v1-frozen`.

## What is frozen

Everything under `src/`, `configs/` and `pyproject.toml` at the tag:

- validation rules, including the dead-signal threshold of 0.01 RMS
  (`bearingguard.data.validate`);
- feature definitions: time-domain features plus envelope SNR at BPFO/BPFI/BSF with
  a 1–9 kHz band, ±2% tolerance, 3 harmonics and a 10–500 Hz noise floor
  (`bearingguard.features`);
- the candidate methods, thresholds, grids, primary settings, seeds,
  calibration lengths, restart re-centering, persistence rule, final detection
  window and metric definitions in `configs/protocol_v1.toml`;
- the runner (`bearingguard.experiments.detect`) and the report generator
  (`bearingguard.reporting`).

`bearingguard.experiments.holdout` refuses to run unless the working tree is
clean, HEAD descends from the tag, and `src/`, `configs/` and `pyproject.toml`
are identical to the tag (`tests/test_holdout_guard.py`).

## No selection on the holdout

All seven methods and their full sensitivity grids are evaluated on test 3 and
reported. The primary settings (k = 3, α = 0.05, seed 0) were declared before
the development run. No method, setting or feature is chosen using test 3.

## Test 3 extra files

**Facts, established without reading signal contents:**

- The archive (MD5 `57b2e74587d73b5485fe0d55731e1331`) extracts test 3 to
  `4th_test/txt/` with 6,324 snapshot files.
- The readme documents 4,448 files from 2004-03-04 09:27:46 to 2004-04-04
  19:01:57. The 4,448th file by timestamp is exactly `2004.04.04.19.01.57`.
- 1,876 further files continue at the regular 10-minute cadence
  (`2004.04.04.19.11.57` onward) until 2004-04-18 02:42:55, with one gap of
  7.3 h before 2004-04-15 10:21:53.
- The readme states that the bearing 3 outer-race failure occurred "at the end
  of the test-to-failure experiment" and gives the end as 2004-04-04 19:01:57.

**Decision.** The only documented failure label is tied to the documented end
time. Nothing documents what happened to the rig or bearings after it, so:

| Analysis | Range | End of test (lead times measured to) | Status |
|---|---|---|---|
| `holdout_v1_documented` | files up to 2004-04-04 19:01:57 (4,448 files) | 2004-04-04 19:01:57 | **primary** |
| `holdout_v1_full_archive` | all 6,324 files | last usable file | secondary, reported separately |

Both analyses are fixed here, before either is run. If they disagree, the
primary analysis is not replaced by the secondary one, and the disagreement is
reported. File-size and contents checks of the extra files were deliberately
**not** used: ASCII file size depends on signal amplitude, so it would leak
signal information before the freeze.

## Procedure

```bash
# working tree clean, at or after the tag, no changes to src/configs since
python -m bearingguard.experiments.holdout --tag protocol-v1-frozen
```

The command:

1. checks the freeze conditions;
2. validates all test 3 files with the frozen rules and writes
   `derived/manifest_test3.csv`; invalid or dead files are excluded and listed;
3. builds the time and spectral features for test 3;
4. runs `configs/protocol_v1.toml` with only `name`, `tests = [3]` and
   `restrict_to_documented_end` changed (checked in code), once per analysis;
5. writes `runs/holdout_v1_{documented,full_archive}/` and the reports in
   `docs/results/holdout_v1_{documented,full_archive}/`.

Each run records the Git commit, `allow_sealed = true`, and SHA-256 hashes of the
test 3 manifest and feature files.

## Deviations

- The first execution is the holdout result. Its outputs are committed as-is.
- If it exposes a bug, the bug is documented next to the results. Any fix goes
  into a new protocol version (`protocol_v2`, new tag). Results from such a
  rerun are labelled exploratory and never replace the v1 holdout numbers.
- Test 3 is evaluated with each bearing's own first 144 usable snapshots as
  calibration, exactly as for tests 1 and 2. No test 3 data enters any
  development decision.
