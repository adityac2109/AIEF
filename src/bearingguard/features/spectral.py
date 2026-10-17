"""Frequency-domain condition indicators for one 1 s snapshot channel.

Purpose: the time-domain indicators respond to any change in vibration,
including rig-wide gain shifts (see docs/results/calibration_study.md).
These features target bearing-specific damage and are ratios, so a uniform
change in signal gain cancels out.

envelope SNR at BPFO / BPFI / BSF
    A local defect produces impacts at a defect frequency. Each impact excites
    high-frequency structural resonances, so the defect frequency appears in the
    *envelope* of the band-passed signal rather than in the raw spectrum
    (Randall & Antoni 2011). Steps:
      1. band-pass ENVELOPE_BAND (zero-phase Butterworth, within this snapshot only)
      2. envelope = |analytic signal| (Hilbert transform), mean removed
      3. amplitude spectrum of the envelope (Hann window, ~0.98 Hz resolution)
      4. for harmonics h = 1..3 of the defect frequency, take the peak within
         +/- FREQ_TOLERANCE (slip and small speed variation), and sum them
      5. divide by the median envelope-spectrum amplitude in NOISE_BAND
    The band is fixed in advance, not chosen per bearing (a kurtogram would
    pick it adaptively), which costs some sensitivity but cannot be tuned to
    the outcome.

hf_energy_ratio
    Share of signal power above HF_CUTOFF_HZ. Impacts and surface damage add
    broadband high-frequency energy before overall RMS rises much.

Units: the amplitudes cancel in every feature, so the undocumented
acceleration units do not matter. All features use only this snapshot.
"""

from __future__ import annotations

import numpy as np
from scipy.signal import butter, hilbert, sosfiltfilt

from bearingguard.data.ims import SAMPLING_RATE_HZ, SHAFT_SPEED_RPM
from bearingguard.features.bearing import ZA_2115

ENVELOPE_BAND = (1_000.0, 9_000.0)
NOISE_BAND = (10.0, 500.0)
HF_CUTOFF_HZ = 5_000.0
FREQ_TOLERANCE = 0.02
N_HARMONICS = 3
DEFECTS = ("bpfo", "bpfi", "bsf")

SPECTRAL_FEATURE_NAMES = tuple(f"env_{d}" for d in DEFECTS) + ("hf_energy_ratio",)

_DEFECT_HZ = ZA_2115.defect_frequencies(SHAFT_SPEED_RPM / 60.0)


def envelope_spectrum(x: np.ndarray, fs: float = SAMPLING_RATE_HZ,
                      band: tuple[float, float] = ENVELOPE_BAND) -> tuple[np.ndarray, np.ndarray]:
    sos = butter(4, band, btype="bandpass", fs=fs, output="sos")
    env = np.abs(hilbert(sosfiltfilt(sos, x)))
    env -= env.mean()
    spec = np.abs(np.fft.rfft(env * np.hanning(len(env)))) / len(env)
    return np.fft.rfftfreq(len(env), d=1.0 / fs), spec


def _band_peak(freqs: np.ndarray, spec: np.ndarray, center: float, tol: float) -> float:
    mask = (freqs >= center * (1 - tol)) & (freqs <= center * (1 + tol))
    return float(spec[mask].max()) if mask.any() else 0.0


def spectral_features(x: np.ndarray, fs: float = SAMPLING_RATE_HZ,
                      defect_hz: dict[str, float] | None = None) -> dict[str, float]:
    x = np.asarray(x, dtype=np.float64)
    if x.ndim != 1 or x.size < 1024:
        raise ValueError("expected a 1-D signal with at least 1024 samples")
    if np.ptp(x) == 0:
        raise ValueError("constant signal: spectral features undefined")
    defect_hz = defect_hz or _DEFECT_HZ

    freqs, spec = envelope_spectrum(x, fs)
    noise = spec[(freqs >= NOISE_BAND[0]) & (freqs <= NOISE_BAND[1])]
    floor = float(np.median(noise))
    if floor <= 0:
        raise ValueError("envelope noise floor is zero")
    out = {}
    for d in DEFECTS:
        peaks = [_band_peak(freqs, spec, h * defect_hz[d], FREQ_TOLERANCE)
                 for h in range(1, N_HARMONICS + 1)]
        out[f"env_{d}"] = sum(peaks) / floor

    power = np.abs(np.fft.rfft(x - x.mean())) ** 2
    pf = np.fft.rfftfreq(len(x), d=1.0 / fs)
    out["hf_energy_ratio"] = float(power[pf >= HF_CUTOFF_HZ].sum() / power.sum())
    return out
