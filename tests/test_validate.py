import csv

import pytest

from bearingguard.data.ims import SealedTestError, extracted_dir, get_spec
from bearingguard.data.validate import (
    STATUS_DEAD,
    STATUS_INVALID,
    STATUS_OK,
    validate_test,
    write_manifest,
)


@pytest.fixture
def test2_dir(tmp_path, make_snapshot):
    root = extracted_dir(tmp_path, 2) / "2nd_test"
    make_snapshot(root / "2004.02.12.10.32.39")
    make_snapshot(root / "2004.02.12.10.42.39")
    make_snapshot(root / "2004.02.13.09.02.39")  # overnight-style gap
    make_snapshot(root / "2004.02.13.09.12.39", scale=0.001)  # no vibration signal
    make_snapshot(root / "2004.02.13.09.22.39", n_rows=100)  # truncated
    return tmp_path


def test_validate_flags_each_problem_explicitly(test2_dir):
    records = validate_test(test2_dir, 2)

    assert [r.status for r in records] == [
        STATUS_OK, STATUS_OK, STATUS_OK, STATUS_DEAD, STATUS_INVALID,
    ]
    assert "channel(s) [1, 2, 3, 4]" in records[3].reason
    assert records[1].interval_s == 600
    assert records[2].interval_s == pytest.approx(22.33 * 3600, abs=60)


def test_validate_refuses_sealed_test(tmp_path):
    with pytest.raises(SealedTestError):
        validate_test(tmp_path, 3)


def test_validate_raises_when_no_files(tmp_path):
    with pytest.raises(FileNotFoundError):
        validate_test(tmp_path, 1)


def test_manifest_has_one_row_per_file(test2_dir, tmp_path):
    records = validate_test(test2_dir, 2)
    out = tmp_path / "manifest.csv"
    write_manifest(records, get_spec(2), out)

    with out.open() as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == len(records)
    assert rows[4]["status"] == STATUS_INVALID and rows[4]["rms_ch1"] == ""
    assert float(rows[0]["rms_ch1"]) == pytest.approx(0.1, rel=0.05)
