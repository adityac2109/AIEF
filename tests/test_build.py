import pytest

from bearingguard.data.ims import SealedTestError, extracted_dir, get_spec
from bearingguard.data.validate import validate_test, write_manifest
from bearingguard.features.build import (
    build_features,
    features_path,
    load_features,
    manifest_path,
)
from bearingguard.features.spectral import SPECTRAL_FEATURE_NAMES


@pytest.fixture
def data_dir(tmp_path, make_snapshot):
    root = extracted_dir(tmp_path, 2) / "2nd_test"
    for name in ["2004.02.12.10.32.39", "2004.02.12.10.42.39"]:
        make_snapshot(root / name)
    make_snapshot(root / "2004.02.12.10.52.39", scale=0.001)  # dead: must be skipped
    write_manifest(validate_test(tmp_path, 2), get_spec(2), manifest_path(tmp_path, 2))
    return tmp_path


def test_sets_are_built_separately_and_merged_on_load(data_dir):
    for s in ("time", "spectral"):
        build_features(data_dir, 2, s, workers=1).to_csv(features_path(data_dir, 2, s), index=False)

    merged = load_features(data_dir, 2, sets=("time", "spectral"))

    assert len(merged) == 2 * 4  # two ok snapshots x four bearings; dead file excluded
    assert {"rms", "kurtosis", *SPECTRAL_FEATURE_NAMES} <= set(merged.columns)
    assert features_path(data_dir, 2, "time") != features_path(data_dir, 2, "spectral")


def test_missing_feature_set_reports_build_command(data_dir):
    with pytest.raises(FileNotFoundError, match="--set spectral"):
        load_features(data_dir, 2, sets=("spectral",))


def test_sealed_test_refused_without_opt_in(tmp_path):
    with pytest.raises(SealedTestError):
        build_features(tmp_path, 3, "spectral")
    with pytest.raises(SealedTestError):
        load_features(tmp_path, 3)
