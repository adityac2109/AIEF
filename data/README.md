# Data

Raw and derived data are **not** stored in this repository. The extracted IMS
data is ~5 GB of ASCII text, so it lives in a directory you choose, ideally
outside any cloud-synced folder.

## Source

NASA IMS Bearings dataset, provided by the NSF I/UCR Center for Intelligent
Maintenance Systems (University of Cincinnati) with support from Rexnord Corp.

- Catalog page: https://data.nasa.gov/dataset/ims-bearings
- Archive: https://data.nasa.gov/docs/legacy/IMS.zip (1,061,902,801 bytes,
  MD5 `57b2e74587d73b5485fe0d55731e1331`, checked 2026-10-16)
- License: U.S. Government Works
- Reference paper (as cited in the dataset readme): Hai Qiu, Jay Lee, Jing Lin,
  "Wavelet Filter-based Weak Signature Detection Method and its Application on
  Roller Bearing Prognostics," *Journal of Sound and Vibration* 289 (2006) 1066–1090.

## Automated setup

```bash
# Windows PowerShell:  $env:BEARINGGUARD_DATA_DIR = "C:\data\ims"
# bash:                export BEARINGGUARD_DATA_DIR=/path/to/ims
python -m bearingguard.data.download   # download, verify MD5, extract
python -m bearingguard.data.validate --test 1 2
```

Extraction needs a RAR-capable `tar` (bsdtar/libarchive). It ships with
Windows 10+ (`C:\Windows\System32\tar.exe`) and macOS. On Linux install
`libarchive-tools` or use the manual route.

## Manual setup

1. Download `IMS.zip` from the catalog page into `$BEARINGGUARD_DATA_DIR/raw/`.
2. Extract `IMS/1st_test.rar`, `IMS/2nd_test.rar` and `IMS/3rd_test.rar` from the
   zip, then extract each into `raw/test1/`, `raw/test2/` and `raw/test3/`.
   The internal folder layout does not matter; snapshot files are found by name.
3. Run `python -m bearingguard.data.download`. It skips anything already present,
   verifies the zip checksum, and reports file counts against the readme.

## Layout

```
$BEARINGGUARD_DATA_DIR/
  raw/IMS.zip
  raw/test{1,2,3}/...            one file per snapshot, named YYYY.MM.DD.hh.mm.ss
  derived/manifest_test{N}.csv   per-file validation status (from validate)
```

## Facts from the dataset readme

| | Test 1 | Test 2 | Test 3 |
|---|---|---|---|
| Recording | 2003-10-22 → 2003-11-25 | 2004-02-12 → 2004-02-19 | 2004-03-04 → 2004-04-04 |
| Files | 2,156 | 984 | 4,448 |
| Channels | 8 (x/y per bearing) | 4 | 4 |
| Failure at end of test | bearing 3 inner race, bearing 4 roller element | bearing 1 outer race | bearing 3 outer race |

All tests ran at 2000 RPM under a 6000 lb radial load on Rexnord ZA-2115 bearings.
Each file is a 1 s snapshot of 20,480 samples at 20 kHz, recorded every 10 minutes
(the first 43 files of test 1 every 5 minutes). Longer gaps between file timestamps
mean the experiment resumed the next working day.

**Not documented:** measurement units (often assumed to be g; this project
treats them as unknown), which test 1 channel is the x axis and which is y,
and when each fault began. The only failure information is the state at the
end of each test.

## Observed differences from the readme

Found by `download` and `validate` on the archive with MD5 `57b2e745…`:

- **Test 3 contains 6,324 files, not 4,448.** The archive extracts to
  `4th_test/txt/`. The first 4,448 files end exactly at the documented end time
  (2004-04-04 19:01:57). After that, 1,876 undocumented files continue until
  2004-04-18 02:42:55. This was established from filenames only; no test 3
  signal contents were read. The readme places the bearing 3 failure "at the end
  of the test". How the holdout treats these files was decided before unsealing:
  see [docs/holdout_protocol.md](../docs/holdout_protocol.md).
- **Test 1 has 145 five-minute intervals, not 43 files.** Forty of them fall in
  the first 43 files, as documented; the rest occur later in the run. Test 1 also
  has 21 gaps longer than 1 h, the longest 148 h.
- **The last two files of test 2** (2004.02.19.06.12.39 and 06.22.39) carry no
  vibration signal: every channel's RMS is ≤ 0.0040, against ≥ 0.0537 for any
  running file. `validate` marks them `dead_signal`.

All 2,156 test 1 files and 984 test 2 files match the documented shape
(20,480 × 8 and 20,480 × 4) and contain only finite numeric values.

## Test 3 is sealed

Test 3 is the final holdout. `bearingguard.data.ims.get_spec(3)` raises
`SealedTestError` unless it is called with `allow_sealed=True`, which only the
frozen final evaluation should do. The download step counts test 3 files but
never reads their contents.
