import numpy as np
import pytest

from bearingguard.features.time_domain import FEATURE_NAMES, time_domain_features


def test_sine_has_textbook_values():
    t = np.arange(20_480) / 20_000
    f = time_domain_features(2.0 * np.sin(2 * np.pi * 100 * t))

    assert f["rms"] == pytest.approx(2.0 / np.sqrt(2), rel=1e-3)
    assert f["crest_factor"] == pytest.approx(np.sqrt(2), rel=1e-3)
    assert f["kurtosis"] == pytest.approx(1.5, rel=1e-2)
    assert f["skewness"] == pytest.approx(0.0, abs=1e-2)
    assert f["peak_to_peak"] == pytest.approx(4.0, rel=1e-3)


def test_gaussian_kurtosis_is_about_three():
    x = np.random.default_rng(0).normal(size=200_000)
    assert time_domain_features(x)["kurtosis"] == pytest.approx(3.0, abs=0.05)


def test_impulses_raise_kurtosis_and_crest_factor():
    rng = np.random.default_rng(1)
    base = rng.normal(0, 1, 20_480)
    impulsive = base.copy()
    impulsive[::500] += 15.0  # periodic impacts, as from a local defect
    a, b = time_domain_features(base), time_domain_features(impulsive)
    assert b["kurtosis"] > a["kurtosis"] + 1
    assert b["crest_factor"] > a["crest_factor"]


def test_returns_every_named_feature():
    assert set(time_domain_features(np.arange(10.0))) == set(FEATURE_NAMES)


def test_constant_signal_rejected():
    with pytest.raises(ValueError, match="constant"):
        time_domain_features(np.ones(100))


def test_non_1d_rejected():
    with pytest.raises(ValueError):
        time_domain_features(np.ones((10, 2)))
