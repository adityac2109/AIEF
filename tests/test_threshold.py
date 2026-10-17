import numpy as np
import pytest

from bearingguard.models.threshold import ZScoreThreshold


def test_fit_uses_only_calibration_statistics():
    calib = np.array([[1.0], [2.0], [3.0]])  # mean 2, sample std 1
    m = ZScoreThreshold(k=3).fit(calib)
    np.testing.assert_allclose(m.score(np.array([[2.0], [5.0], [5.1]])).ravel(), [0, 3, 3.1])


def test_exceed_is_one_sided_and_strict():
    m = ZScoreThreshold(k=3).fit(np.array([[1.0], [2.0], [3.0]]))
    assert m.exceed(np.array([[5.0], [5.1], [-10.0]])).ravel().tolist() == [False, True, False]


def test_zero_variance_calibration_rejected():
    with pytest.raises(ValueError, match="zero variance"):
        ZScoreThreshold(k=3).fit(np.array([[1.0, 2.0], [1.0, 3.0]]))


def test_score_before_fit_rejected():
    with pytest.raises(RuntimeError):
        ZScoreThreshold(k=3).score(np.zeros((1, 1)))
