# Detector comparison on development tests 1–2

**Status: development (exploratory) results.** Test 3 is not used here. All
methods in this comparison are carried unchanged to the holdout
([../holdout_protocol.md](../holdout_protocol.md)), so nothing below is used to
pick a winner.

Generated tables and figures: [protocol_v1_dev/summary.md](protocol_v1_dev/summary.md)
(run `protocol_v1_dev`, commit `467543d`, clean tree, runtime 171 s).
Protocol: [../experiment_protocol.md](../experiment_protocol.md).

## Methods

| Method | Score | Features | Threshold | Restart re-centering |
|---|---|---|---|---|
| `zscore_time_raw` | per-feature z, alarm if any z > k | RMS, kurtosis, crest factor | k·σ of calibration | no (original baseline) |
| `zscore_time` | same | same | same | yes |
| `zscore_time_env` | same | + envelope SNR at BPFO, BPFI, BSF | same | yes |
| `iforest_time` | Isolation Forest | time features | k·σ of held-out calibration scores | yes |
| `iforest_time_env` | Isolation Forest | time + envelope | same | yes |
| `iforest_time_pvalue` | Isolation Forest | time features | calibration p-value ≤ α | yes |
| `iforest_time_env_pvalue` | Isolation Forest | time + envelope | same | yes |

Primary settings, declared before the run: k = 3, α = 0.05, Isolation Forest seed 0.
Sensitivity grids: k ∈ {3, 4, 5, 6}, α ∈ {0.1, 0.05, 1/49}, 5 seeds.

## Measured results (primary settings)

| Method | Failed detected | First-alarm lead, h (T1B3 / T1B4 / T2B1) | Early-half episodes on failed | Non-failed episodes / 100 h | Non-failed time in alarm |
|---|---|---|---|---|---|
| zscore_time_raw | 3/3 | 321 / 308 / 74 | 1 / 19 / 1 | 1.13 | 53.7% |
| zscore_time | 2/3 | 215 / 103 / 74 | 2 / 0 / 1 | 1.97 | 18.0% |
| zscore_time_env | 3/3 | 227 / 297 / 74 | 3 / 17 / 1 | 2.16 | 18.2% |
| iforest_time | 3/3 | 227 / 278 / 55 | 11 / 4 / 0 | 6.95 | 13.2% |
| iforest_time_env | 3/3 | 215 / 298 / 54 | 3 / 27 / 0 | 3.47 | 3.9% |
| iforest_time_pvalue | 3/3 | 288 / 278 / 74 | 26 / 9 / 1 | 11.45 | 26.2% |
| iforest_time_env_pvalue | 3/3 | 279 / 310 / 63 | 21 / 33 / 0 | 10.14 | 12.3% |

"Detected" = in alarm at some point in the bearing's last 24 operating hours.

1. **No method is best on every measure.** The lowest non-failed time in alarm
   (`iforest_time_env`, 3.9%) comes with the most early-half episodes on T1B4 (27).
   The fewest early-half episodes (`zscore_time`) comes with a missed detection.
2. **Restart re-centering can mask a failure.** `zscore_time` misses T1B4: its
   alarm stops around operating hour 290, and the restart re-centering at hour
   338 absorbs the elevated level before the end of the test (see
   `alarm_raster_test1.png`).
3. **Envelope features restore that detection** (`zscore_time_env`: 3/3), at the
   cost of 17 early-half episodes on T1B4.
4. **The envelope SNR tracks the documented defect for two of three failures.**
   BPFI rises at the end of T1B3 (inner race) and BPFO at the end of T2B1 (outer
   race). For T1B4 (roller element) the BSF band stays near its baseline, while the
   BPFO band rises sharply at the end (`envelope_failed.png`). The data cannot say
   whether that reflects secondary outer-race damage or a weak BSF signature.
5. **The high-frequency energy ratio was dropped.** Before it entered any detector,
   its median fell over the last 5% of test 2 on all four bearings, which
   contradicts the one-sided assumption that indicators rise with damage.
6. **Isolation Forest's raw score saturates.** Once a point leaves the training
   range it is isolated in one or two splits, so a 50σ departure scores barely
   higher than a 5σ one (`tests/test_detect.py`). On the real data the k·σ rule
   still fires, but raising k cuts alarms abruptly: at k = 6, `iforest_time_env`
   detects only 2/3 and raises no non-failed alarms.
7. **Seeds:** across 5 Isolation Forest seeds, every method detects 3/3. The
   non-failed alarm rate varies by up to 1.5× (`iforest_time_env`: 2.44–3.57
   episodes per 100 h).

## Does the calibration p-value deliver its nominal rate?

The p-value threshold promises P(p ≤ α) ≤ α per snapshot **only if** new scores
are exchangeable with the 48 held-out calibration scores. Measured on the five
non-failed bearings (seed 0):

| Method | α | First 48 scored snapshots | First half of run | Whole run |
|---|---|---|---|---|
| iforest_time_env_pvalue | 0.05 | 0.033 (max 0.083) | 0.095 (max 0.232) | 0.179 (max 0.258) |
| iforest_time_env_pvalue | 1/49 | 0.008 (max 0.042) | 0.029 (max 0.105) | 0.078 (max 0.191) |
| iforest_time_pvalue | 0.05 | 0.067 (max 0.146) | 0.176 (max 0.418) | 0.285 (max 0.604) |

- **Right after calibration** the observed rate is close to α on average
  (0.033 at α = 0.05 for the time + envelope variant).
- **Later in the run** it rises above α: over the whole run, 0.179 at α = 0.05
  (3.6×) for the time + envelope variant and 0.285 (5.7×) for time features
  alone. The rig drifts and restarts, so later
  scores are not exchangeable with early ones, and the nominal rate does not
  carry over. The "non-failed" bearings may also be degrading or picking up
  vibration from their neighbours, so part of this excess may be real signal.
- **Even when exchangeability holds**, 48 calibration scores leave a single
  bearing's false-exceedance rate widely spread around α; the guarantee holds
  on average over calibration draws, not for one draw
  (`tests/test_detectors.py::test_pvalues_are_marginally_valid_under_exchangeability`).

**Conclusion for H3:** on these data the calibration p-value is a well-defined,
interpretable threshold, but not a statistical guarantee on false alarms. Its
alarm-level trade-off is not better than k·σ on the same score: at α = 0.05 it
raises 10.14 non-failed episodes per 100 h against 3.47 for k = 3, and both
detect 3/3. We therefore describe it as *calibration-quantile thresholding*,
not as conformal prediction with coverage guarantees.

## Limitations

- Three failed and five non-failed bearings in two tests. These are case
  studies; no statistical significance is claimed.
- Lead time, "detected" and false alarms all depend on proxy labels (failure
  only documented at the end of each test).
- One channel per bearing, a fixed envelope band (no per-bearing band selection),
  and one calibration length (144 snapshots) were examined.
