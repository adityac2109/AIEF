import numpy as np
import pytest

from bearingguard.evaluation.alarms import (
    alarm_metrics,
    episode_starts,
    operating_hours,
    persistent_alarm,
    restart_triggered_episodes,
)


def ts(minutes):
    return np.datetime64("2004-02-12T00:00:00") + np.array(minutes, dtype="timedelta64[m]")


def test_persistence_requires_r_of_last_m():
    ex = np.array([1, 0, 1, 0, 1, 1, 0, 0, 0], dtype=bool)
    assert persistent_alarm(ex, required=3, window=5).tolist() == [
        False, False, False, False, True, True, True, False, False,
    ]


def test_single_spike_does_not_alarm_with_persistence():
    ex = np.zeros(20, dtype=bool)
    ex[10] = True
    assert not persistent_alarm(ex, required=3, window=5).any()


def test_persistence_is_causal():
    ex = np.array([0, 1, 1, 0, 1, 0, 0, 1, 1, 1], dtype=bool)
    changed = ex.copy()
    changed[6:] = ~changed[6:]  # alter only the future
    a, b = persistent_alarm(ex, 3, 5), persistent_alarm(changed, 3, 5)
    assert a[:6].tolist() == b[:6].tolist()


def test_invalid_persistence_rejected():
    with pytest.raises(ValueError):
        persistent_alarm(np.zeros(3, bool), required=4, window=3)


def test_episode_starts():
    assert episode_starts(np.array([0, 1, 1, 0, 0, 1, 0, 1], bool)).tolist() == [1, 5, 7]


def test_operating_hours_skip_long_gaps():
    # 10 min steps, then a 20 h overnight gap, then 10 min steps
    hours = operating_hours(ts([0, 10, 20, 1220, 1230]), max_gap_s=3600)
    np.testing.assert_allclose(hours, [0, 1 / 6, 2 / 6, 2 / 6, 3 / 6])


def test_alarm_metrics_lead_time_and_rates():
    t = ts(np.arange(0, 24 * 60 * 2, 10))  # 2 days at 10 min
    alarm = np.zeros(len(t), bool)
    alarm[10:12] = True      # early episode (first half)
    alarm[-6:] = True        # final episode, 50 min before the last snapshot
    m = alarm_metrics(t, alarm, max_gap_s=3600)

    assert m["episodes"] == 2
    assert m["early_half_episodes"] == 1
    assert m["first_alarm_lead_h"] == pytest.approx(m["monitored_hours"] - 100 / 60)
    assert m["episodes_per_day"] == pytest.approx(2 / (m["monitored_hours"] / 24))


def test_alarm_metrics_without_alarms():
    m = alarm_metrics(ts([0, 10, 20]), np.zeros(3, bool), max_gap_s=3600)
    assert m["episodes"] == 0 and np.isnan(m["first_alarm_lead_h"])


def test_restart_triggered_episodes_counts_only_shortly_after_long_gaps():
    # session 1: 0..50 min; 10 h shutdown; session 2 from 650 min
    minutes = list(range(0, 60, 10)) + list(range(650, 1650, 10))
    t = ts(minutes)
    alarm = np.zeros(len(t), bool)
    alarm[2:4] = True  # before any restart: not counted
    i, j = minutes.index(700), minutes.index(1500)
    alarm[i:i + 2] = True  # 50 min after the restart: counted
    alarm[j:j + 2] = True  # 14 h after the restart: not counted
    assert restart_triggered_episodes(t, alarm, restart_gap_s=8 * 3600, window_h=6) == 1
    assert restart_triggered_episodes(t, alarm, restart_gap_s=24 * 3600, window_h=6) == 0
