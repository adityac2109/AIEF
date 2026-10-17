# Calibration study: restart shifts in IMS test 1

Development data only (tests 1 and 2); test 3 untouched. Protocol and metric
definitions: [../experiment_protocol.md](../experiment_protocol.md). Full
generated tables for k ∈ {3, 4, 5, 6} and run provenance:
[calibration_study_tables.md](calibration_study_tables.md). All runs are
from commit `e8ff932` with a clean tree.

## Motivation

In the per-bearing k-σ baseline, RMS alarms on test 1 bearings 1, 2 and 3 all
start at 2003-10-29 14:59:46, just after a 148 h shutdown, and stay on for
99.3% of the remaining snapshots. Mean RMS over the two days after that restart,
compared with the 144-snapshot calibration window:

| Bearing | B1 | B2 | B3 | B4 |
|---|---|---|---|---|
| RMS change | +18.3% | +14.2% | +21.5% | +21.6% |

A simultaneous shift on all four bearings, including two that did not fail,
points to a change in the rig or measurement chain at the restart rather than
bearing damage. The cause is not documented. This study asks whether that
shift can be handled without hiding real degradation.

<details><summary>Reproduce the shift table</summary>

```python
import pandas as pd
f = pd.read_csv(r"<DATA_DIR>/derived/features_test1.csv", parse_dates=["timestamp"])
f = f[f["axis"] == 0]
restart = pd.Timestamp("2003-10-29 14:39:46")
cal_end = sorted(f["timestamp"].unique())[143]
for b, g in f.groupby("bearing"):
    cal = g.loc[g["timestamp"] <= cal_end, "rms"].mean()
    post = g.loc[(g["timestamp"] >= restart) & (g["timestamp"] < restart + pd.Timedelta("2D")), "rms"].mean()
    print(b, f"{100 * (post / cal - 1):+.1f}%")
```
</details>

## Results at k = 3, detector `any`

| Method | Lead time, h (T1B3 / T1B4 / T2B1) | Early-half episodes, failed | Non-failed bearings alarmed | Non-failed time in alarm | Restart-triggered episodes | Blind, test 1 |
|---|---|---|---|---|---|---|
| Baseline | 321 / 308 / 74 | 1 / 19 / 1 | 5/5 | 53.7% | 14 | 0% |
| Re-center, gap ≥ 8 h | 215 / 103 / 74 | 2 / 0 / 1 | 5/5 | 18.0% | 4 | 8.9% |
| Re-center, gap ≥ 1 h | 215 / 103 / 74 | 2 / 0 / 1 | 4/5 | 15.0% | 4 | 17.4% |
| Re-center, gap ≥ 24 h | 298 / 307 / 74 | 5 / 14 / 1 | 5/5 | 19.3% | 9 | 3.6% |
| Cross-bearing log ratio | 300 / 306 / 78 | 26 / 16 / 3 | 2/5 | 8.4% | 38 | 0% |

Test 2 has no gaps over 1 h, so the re-centering variants leave its results
unchanged by construction.

## Measured findings

1. **Re-centering at 8 h removes most restart-triggered alarms.** They fall
   from 14 to 4, and early-half episodes on T1B4 from 19 to 0. Non-failed time
   in alarm falls from 53.7% to 18.0%. The cost is 8.9% of test 1 left unscored,
   and shorter lead times on T1B3 (321 → 215 h) and T1B4 (308 → 103 h).
2. **Re-centering too often can hide damage.** At a 1 h gap threshold, the RMS
   detector never alarms on the failed bearing T1B4 (see the full tables). The
   last days of test 1 are split into many short sessions, and each restart
   re-baselines the growing vibration.
3. **Re-centering too rarely keeps the artifact.** At 24 h, restart-triggered
   episodes stay at 9 and T1B4 keeps 14 early-half episodes.
4. **Cross-bearing normalization behaves differently in the two tests.** In test 2
   it silences non-failed bearings B2 and B3, with T2B4 still alarming. In test 1
   it *increases* restart-triggered episodes to 38, mostly on B1 (16) and on
   the failed bearings. The restart shifts were not equal across bearings
   (+14.2% to +21.6%), so a log ratio does not cancel them.
5. **Under re-centering (8 h), the remaining non-failed alarms are late.**
   T1B1 alarms once, 10 min before the end of the test. T1B2 alarms from 79 h
   before the end, while T1B3 and T1B4 were deteriorating. All three test 2
   non-failed bearings alarm 15–54 h before the end.

## Interpretation (not established by these data alone)

- The baseline's 300 h+ lead times on test 1 are largely restart artifacts, not
  early detection. Lead times after re-centering are the more credible figures,
  but with no fault-onset labels they cannot be verified.
- Late alarms on non-failed bearings fit vibration from the failing bearing
  reaching nearby sensors, but this was not tested directly.
- Neither method is uniformly better. Re-centering targets restarts; cross-bearing
  normalization targets shared drift but needs the shift to be equal on every
  bearing, and that did not hold here.

## Limitations

- **Three failed and five non-failed bearings** across two tests. These results
  describe cases; they do not support statistical comparisons between methods.
- All metrics depend on the proxy labels in the protocol.
- All settings were fixed before results were seen. Only the gap threshold was
  varied; the restart window (18 snapshots) and the diagnostic window (6 h)
  were each tried at a single value.
- Choosing a method from this study uses tests 1 and 2. That is legitimate
  development use, but it means test 1's restart pattern shaped the method, and
  only test 3 can show whether the choice generalizes.

## Implication for next steps

Restart re-centering at 8 h is the working calibration for the next detectors
(Isolation Forest, conformal thresholds). Cross-bearing normalization stays an
option for test 2-style shared drift, but not as the default. Re-centering
applied *to* cross-bearing ratios is an untested combination and would need its
own pre-registered config.
