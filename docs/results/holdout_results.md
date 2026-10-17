# Holdout results: IMS test 3 (protocol v1)

**Status: final holdout evaluation, executed once** under the frozen protocol
([../holdout_protocol.md](../holdout_protocol.md)), tag `protocol-v1-frozen`,
commit `9e61758`. Generated outputs, unedited:

- primary: [holdout_v1_documented/summary.md](holdout_v1_documented/summary.md)
- secondary: [holdout_v1_full_archive/summary.md](holdout_v1_full_archive/summary.md)

## Data validation (frozen rules)

6,324 files: 6,323 usable. The last file, `2004.04.18.02.42.55`, carries no
signal on any channel (RMS < 0.01) and was excluded, as at the end of test 2.
There are 4 gaps over 1 h (the longest 7.5 h), so no restart re-centering was
triggered (threshold 8 h). Blind time is 0%, and `zscore_time` is identical
to `zscore_time_raw` on this test.

## Primary analysis: documented range (to 2004-04-04 19:01:57)

| Method | T3B3 detected | First-alarm lead, h | Early-half episodes, T3B3 | Non-failed episodes / 100 h | Non-failed time in alarm |
|---|---|---|---|---|---|
| zscore_time_raw | no | – | 0 | 0.23 | 0.5% |
| zscore_time | no | – | 0 | 0.23 | 0.5% |
| zscore_time_env | no | 390 | 2 | 0.51 | 0.6% |
| iforest_time | no | – | 0 | 0.00 | 0.0% |
| iforest_time_env | no | 680 | 12 | 0.00 | 0.0% |
| iforest_time_pvalue | no | 715 | 177 | 33.68 | 29.9% |
| iforest_time_env_pvalue | yes | 715 | 169 | 6.28 | 2.7% |

**No method detects the documented failure in a meaningful way.** The single
"detection" (`iforest_time_env_pvalue`) comes from a detector that alarms from
the first hours of the run: 246 episodes on T3B3, 169 of them in the first half,
and 122 episodes on non-failed T3B1.

**Why.** Over the last ~24 h before the documented end, T3B3's mean RMS is at
its calibration level (0.0695 vs 0.0688, z = 0.4), and its median BPFO envelope
SNR is 5.9 vs 5.5 at calibration. The features show no degradation before the
documented end. A k = 3, 3-of-5 RMS rule first fires on T3B3 at 2004-04-15 15:42,
eleven days after the documented end, in the undocumented files.

## Secondary analysis: full archive (to 2004-04-18 02:42:55)

| Method | T3B3 detected | First-alarm lead, h | Non-failed bearings alarmed | Non-failed episodes / 100 h | Non-failed time in alarm |
|---|---|---|---|---|---|
| zscore_time_raw | yes | 59 | 3/3 | 0.39 | 3.4% |
| zscore_time | yes | 59 | 3/3 | 0.39 | 3.4% |
| zscore_time_env | yes | 702 | 3/3 | 0.68 | 3.5% |
| iforest_time | yes | 58 | 0/3 | 0.00 | 0.0% |
| iforest_time_env | yes | 992 | 3/3 | 0.68 | 0.5% |
| iforest_time_pvalue | yes | 1027 | 3/3 | 30.43 | 26.1% |
| iforest_time_env_pvalue | yes | 1027 | 3/3 | 6.29 | 5.0% |

- In the final ~60 operating hours RMS rises steeply on **all four** bearings
  (`holdout_v1_full_archive/figures/alarm_raster_test3.png`). At the end of the
  archive the BPFO envelope SNR is high on every channel: 22.2 on B3, 22.5 on B4,
  15.5 on B2, 9.1 on B1.
- The z-score methods detect T3B3 59 h before the end of the archive, but also
  alarm on all three non-failed bearings in the same period. That detection is
  not bearing-specific.
- `iforest_time` is the only method that detects T3B3 (58 h before the end) with
  no alarm on any non-failed bearing. Its development record was mixed (3/3
  detected but 6.95 non-failed episodes per 100 h), so this is one case, not
  evidence of a better method.
- Lead times of 702–1,027 h come from early, scattered alarms, not from the
  late degradation.

## Interpretation

- On these data, the documented failure time for test 3 and the recorded
  vibration are inconsistent. Either the failure developed after the readme's
  stated end (the archive continues 13 days further), or the readme's dates do
  not describe this archive's files. The primary analysis therefore tests
  detection of a failure that leaves no trace in these features within its range.
  That is a **negative result for the label, not evidence that the detectors
  work or fail**.
- The calibration p-value thresholds behave as on tests 1–2, only more so:
  hundreds of alarm episodes and up to 30% of non-failed time in alarm. The
  nominal false-alarm rate does not hold outside the calibration window.
- The holdout confirms one development finding, that no method dominates. It
  adds one: when degradation is abrupt and rig-wide, per-bearing detectors
  cannot say *which* bearing is failing.

## Deviations from the protocol

1. **Provenance flag on the secondary run.** `runs/holdout_v1_full_archive/metadata.json`
   records `git_dirty: true`. The holdout runner wrote the primary report
   (`docs/results/holdout_v1_documented/`, then untracked) before starting the
   secondary run, and the dirty check counts untracked files. The freeze check
   passed at the start of the command, and no tracked file changed during it.
   This is a defect in the runner's ordering, not a change in code or config.
   The fix (write reports only after all runs) follows in a separate commit
   after these results; the holdout is not rerun.
2. No other deviations. No parameter, feature or method was changed after the
   holdout was read.
