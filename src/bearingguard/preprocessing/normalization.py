"""Cross-bearing normalization of condition indicators.

All four IMS bearings share one shaft, motor and load, and each snapshot
samples them simultaneously. A change that affects the whole rig (for example
after a restart) therefore moves every bearing's features together. Expressing
each bearing relative to the median of the *other* bearings at the same
snapshot cancels that common-mode component:

    r[b, t] = log f[b, t] - median_{j != b} log f[j, t]

Log ratios make multiplicative shifts (a gain change of x% on every channel)
cancel exactly. Only same-snapshot values are used, so nothing from the future
enters.

Known weakness: vibration from a failing bearing also reaches its neighbours'
sensors. That raises the reference and can hide part of the failing bearing's
own increase.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def cross_bearing_log_ratio(df: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    """Replace `features` in a long (timestamp, bearing) table with log ratios.

    Requires every bearing at every timestamp and at least three bearings, so
    that the reference is a median of two or more others.
    """
    out = df.copy()
    n_bearings = df["bearing"].nunique()
    if n_bearings < 3:
        raise ValueError("cross-bearing normalization needs at least 3 bearings")
    if (df.groupby("timestamp")["bearing"].nunique() != n_bearings).any():
        raise ValueError("every timestamp must have a row for every bearing")
    if (df[features] <= 0).any().any():
        raise ValueError("log-ratio normalization needs strictly positive features")

    for f in features:
        wide = np.log(df.pivot(index="timestamp", columns="bearing", values=f))
        ratio = pd.DataFrame(index=wide.index, columns=wide.columns, dtype=float)
        for b in wide.columns:
            ratio[b] = wide[b] - wide.drop(columns=b).median(axis=1)
        long = ratio.stack().rename(f).reset_index()
        out = out.drop(columns=f).merge(long, on=["timestamp", "bearing"], how="left")
    return out[df.columns]
