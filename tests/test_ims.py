from datetime import datetime

import numpy as np
import pytest

from bearingguard.data.ims import (
    SAMPLES_PER_FILE,
    TESTS,
    SealedTestError,
    SnapshotFormatError,
    get_spec,
    list_snapshots,
    parse_timestamp,
    read_snapshot,
)


def test_parse_timestamp():
    assert parse_timestamp("2004.02.12.10.32.39") == datetime(2004, 2, 12, 10, 32, 39)


@pytest.mark.parametrize("name", ["readme.txt", "2004.02.12.10.32", "2004.13.12.10.32.39"])
def test_parse_timestamp_rejects_non_snapshots(name):
    with pytest.raises((SnapshotFormatError, ValueError)):
        parse_timestamp(name)


def test_list_snapshots_sorts_by_time_and_ignores_other_files(tmp_path, make_snapshot):
    for name in ["2004.02.12.10.42.39", "2004.02.12.10.32.39"]:
        make_snapshot(tmp_path / "nested" / name, n_rows=3)
    (tmp_path / "notes.txt").write_text("not data")

    found = list_snapshots(tmp_path)

    assert [p.name for _, p in found] == ["2004.02.12.10.32.39", "2004.02.12.10.42.39"]


def test_read_snapshot_returns_documented_shape(tmp_path, make_snapshot):
    path = make_snapshot(tmp_path / "2004.02.12.10.32.39", n_channels=4)
    data = read_snapshot(path, n_channels=4)
    assert data.shape == (SAMPLES_PER_FILE, 4)
    assert data.dtype == np.float64


def test_read_snapshot_rejects_truncated_file(tmp_path, make_snapshot):
    path = make_snapshot(tmp_path / "2004.02.12.10.32.39", n_rows=SAMPLES_PER_FILE - 1)
    with pytest.raises(SnapshotFormatError, match="shape"):
        read_snapshot(path, n_channels=4)


def test_read_snapshot_rejects_wrong_channel_count(tmp_path, make_snapshot):
    path = make_snapshot(tmp_path / "2003.10.22.12.06.24", n_channels=4)
    with pytest.raises(SnapshotFormatError, match="shape"):
        read_snapshot(path, n_channels=8)


def test_read_snapshot_rejects_non_numeric(tmp_path):
    path = tmp_path / "2004.02.12.10.32.39"
    path.write_text("0.1\tabc\t0.2\t0.3\r\n")
    with pytest.raises(SnapshotFormatError, match="unparseable"):
        read_snapshot(path, n_channels=4)


def test_read_snapshot_rejects_nan(tmp_path, make_snapshot):
    path = make_snapshot(tmp_path / "2004.02.12.10.32.39")
    lines = path.read_text().splitlines()
    lines[5] = "nan\t0.1\t0.1\t0.1"
    path.write_text("\n".join(lines) + "\n")
    with pytest.raises(SnapshotFormatError, match="non-finite"):
        read_snapshot(path, n_channels=4)


def test_test3_is_sealed_by_default():
    with pytest.raises(SealedTestError):
        get_spec(3)
    assert get_spec(3, allow_sealed=True).test_id == 3


def test_development_tests_are_not_sealed():
    assert not get_spec(1).sealed and not get_spec(2).sealed


def test_bearing_channel_map_covers_every_channel_once():
    for spec in TESTS.values():
        cols = sorted(c for chans in spec.bearing_channels.values() for c in chans)
        assert cols == list(range(spec.n_channels))
