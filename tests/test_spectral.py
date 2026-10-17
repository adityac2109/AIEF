import numpy as np
import pytest

from bearingguard.data.ims import SAMPLES_PER_FILE, SAMPLING_RATE_HZ
from bearingguard.features.bearing import ZA_2115
from bearingguard.features.spectral import SPECTRAL_FEATURE_NAMES, spectral_features

FS = SAMPLING_RATE_HZ
T = np.arange(SAMPLES_PER_FILE) / FS


def test_kinematics_match_published_ims_frequencies():
    f = ZA_2115.defect_frequencies(2000 / 60)
    # Published (rounded): BPFO 236, BPFI 297, BSF 139, FTF 15 Hz
    assert f["bpfo"] == pytest.approx(236, abs=1)
    assert f["bpfi"] == pytest.approx(297, abs=1)
    assert f["bsf"] == pytest.approx(139, abs=1)
    assert f["ftf"] == pytest.approx(15, abs=0.5)


def impacts(rate_hz, carrier_hz=4_000.0, seed=0, noise=0.2):
    """Decaying resonance bursts repeating at rate_hz, plus white noise."""
    rng = np.random.default_rng(seed)
    x = rng.normal(0, noise, T.size)
    decay = np.exp(-T[:200] * 2_000) * np.sin(2 * np.pi * carrier_hz * T[:200])
    for t0 in np.arange(0, T[-1] - 0.011, 1 / rate_hz):
        i = int(t0 * FS)
        x[i:i + 200] += decay
    return x


@pytest.mark.parametrize("defect", ["bpfo", "bpfi"])
def test_envelope_identifies_simulated_defect(defect):
    freqs = ZA_2115.defect_frequencies(2000 / 60)
    f = spectral_features(impacts(freqs[defect]))
    others = [v for k, v in f.items() if k.startswith("env_") and k != f"env_{defect}"]
    assert f[f"env_{defect}"] > 3 * max(others)


def test_noise_has_no_strong_defect_peak():
    f = spectral_features(np.random.default_rng(1).normal(size=T.size))
    with_defect = spectral_features(impacts(ZA_2115.defect_frequencies(2000 / 60)["bpfo"]))
    assert with_defect["env_bpfo"] > 5 * f["env_bpfo"]


def test_features_are_gain_invariant():
    x = impacts(236.4, seed=2)
    a, b = spectral_features(x), spectral_features(3.7 * x)
    for k in SPECTRAL_FEATURE_NAMES:
        assert b[k] == pytest.approx(a[k], rel=1e-6)


def test_hf_energy_ratio_tracks_frequency_content():
    low = spectral_features(np.sin(2 * np.pi * 100 * T) + 1e-3 * np.random.default_rng(0).normal(size=T.size))
    high = spectral_features(np.sin(2 * np.pi * 7_000 * T) + 1e-3 * np.random.default_rng(0).normal(size=T.size))
    assert low["hf_energy_ratio"] < 0.01 and high["hf_energy_ratio"] > 0.99


def test_rejects_constant_and_short_signals():
    with pytest.raises(ValueError, match="constant"):
        spectral_features(np.ones(T.size))
    with pytest.raises(ValueError):
        spectral_features(np.ones(100))
