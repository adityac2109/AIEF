"""Turn per-snapshot exceedances into alarms and alarm-level metrics.

There are no fault-onset labels in IMS, so metrics are defined on alarms:
lead time before the end of a run-to-failure test, and how often alarms fire.
Time is measured as operating time: gaps longer than max_gap_s (rig switched
off overnight or between sessions) are not counted.
"""

from __future__ import annotations

import numpy as np


def persistent_alarm(exceed: np.ndarray, required: int, window: int) -> np.ndarray:
    """alarm[t] is True when >= `required` of exceed[t-window+1 .. t] are True.

    Causal: alarm[t] depends only on snapshots up to t.
    """
    if not 1 <= required <= window:
        raise ValueError("need 1 <= required <= window")
    x = np.asarray(exceed, dtype=np.int64)
    csum = np.concatenate([[0], np.cumsum(x)])
    idx = np.arange(1, len(x) + 1)
    counts = csum[idx] - csum[np.maximum(idx - window, 0)]
    return counts >= required


def episode_starts(alarm: np.ndarray) -> np.ndarray:
    """Indices where the alarm switches from off to on (one per alarm episode)."""
    a = np.asarray(alarm, dtype=bool)
    prev = np.concatenate([[False], a[:-1]])
    return np.flatnonzero(a & ~prev)


def operating_hours(timestamps: np.ndarray, max_gap_s: float) -> np.ndarray:
    """Cumulative operating hours at each snapshot, excluding long gaps."""
    t = np.asarray(timestamps, dtype="datetime64[s]").astype(np.int64)
    dt = np.diff(t, prepend=t[0]).astype(np.float64)
    dt[dt > max_gap_s] = 0.0
    return np.cumsum(dt) / 3600.0


def restart_triggered_episodes(timestamps: np.ndarray, alarm: np.ndarray,
                               restart_gap_s: float, window_h: float) -> int:
    """Episodes that start within window_h after a shutdown >= restart_gap_s.

    A diagnostic for alarms caused by rig restarts rather than bearing damage.
    Defined identically for every method so they can be compared.
    """
    t = np.asarray(timestamps, dtype="datetime64[s]").astype(np.int64)
    restarts = t[np.flatnonzero(np.diff(t) >= restart_gap_s) + 1]
    starts = t[episode_starts(alarm)]
    if restarts.size == 0 or starts.size == 0:
        return 0
    # Most recent restart at or before each episode start.
    pos = np.searchsorted(restarts, starts, side="right") - 1
    valid = pos >= 0
    since = starts[valid] - restarts[pos[valid]]
    return int(np.sum(since <= window_h * 3600))


def alarm_in_final_window(timestamps: np.ndarray, alarm: np.ndarray,
                          max_gap_s: float, window_h: float) -> bool:
    """True if the alarm is on at any snapshot in the last window_h operating hours.

    Used as the detection criterion for failed bearings: an alarm that fired
    early and then cleared well before failure does not count as detecting it.
    """
    hours = operating_hours(timestamps, max_gap_s)
    return bool(np.any(np.asarray(alarm, bool)[hours >= hours[-1] - window_h]))


def alarm_metrics(timestamps: np.ndarray, alarm: np.ndarray, max_gap_s: float) -> dict:
    hours = operating_hours(timestamps, max_gap_s)
    total = hours[-1] - hours[0]
    starts = episode_starts(alarm)
    first = starts[0] if starts.size else None
    early = starts[hours[starts] - hours[0] < total / 2] if starts.size else starts
    return {
        "monitored_hours": float(total),
        "episodes": int(starts.size),
        "episodes_per_day": float(starts.size / (total / 24.0)) if total > 0 else float("nan"),
        "alarm_fraction": float(np.mean(alarm)),
        # Operating hours from the first alarm to the last snapshot of the test.
        "first_alarm_lead_h": float(hours[-1] - hours[first]) if first is not None else float("nan"),
        "first_alarm_time": str(np.asarray(timestamps)[first]) if first is not None else "",
        # Episodes starting in the first half of monitored time: a proxy for
        # alarms raised while the bearing was most plausibly still healthy.
        "early_half_episodes": int(early.size),
    }
