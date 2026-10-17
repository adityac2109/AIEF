"""Static report figures drawn from a detect run and the cached feature tables.

Colors follow a fixed categorical order (validated for color-vision
deficiency); every method also has its own marker, and every figure has a
table counterpart in the generated summary, so no reading depends on color alone.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from bearingguard.evaluation.alarms import operating_hours  # noqa: E402
from bearingguard.experiments.threshold_baseline import DIAG_RESTART_GAP_S  # noqa: E402

SURFACE, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7"]
MARKERS = ["o", "s", "^", "D", "v", "P", "X"]
RASTER_METHODS = ["zscore_time_raw", "zscore_time", "iforest_time_env", "iforest_time_env_pvalue"]

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "axes.titlecolor": INK,
    "xtick.color": MUTED, "ytick.color": MUTED, "text.color": INK,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False,
    "font.size": 9, "axes.titlesize": 10, "lines.linewidth": 1.5,
})


def method_style(methods: list[str]) -> dict[str, tuple[str, str]]:
    """Fixed color + marker per method, in config order (never re-ordered by rank)."""
    return {m: (SERIES[i % len(SERIES)], MARKERS[i % len(MARKERS)]) for i, m in enumerate(methods)}


def _segments(hours: np.ndarray, on: np.ndarray, step: float) -> list[tuple[float, float]]:
    segs, start = [], None
    for h, a in zip(hours, on):
        if a and start is None:
            start = h
        elif not a and start is not None:
            segs.append((start, h - start))
            start = None
    if start is not None:
        segs.append((start, hours[-1] + step - start))
    return segs


def alarm_raster(timeline: pd.DataFrame, features: pd.DataFrame, test_id: int,
                 failures: dict[int, str], methods: list[str], out: Path,
                 max_gap_s: float) -> None:
    style = method_style(methods)
    shown = [m for m in RASTER_METHODS if m in methods]
    bearings = sorted(timeline.loc[timeline["test_id"] == test_id, "bearing"].unique())
    fig, axes = plt.subplots(2 * len(bearings), 1, figsize=(10, 2.3 * len(bearings)),
                             gridspec_kw={"height_ratios": [1.6, 1] * len(bearings)}, sharex=True)
    for i, b in enumerate(bearings):
        ax_sig, ax_al = axes[2 * i], axes[2 * i + 1]
        f = features[(features["test_id"] == test_id) & (features["bearing"] == b)].sort_values("timestamp")
        hrs_all = operating_hours(f["timestamp"].to_numpy(), max_gap_s)
        ax_sig.plot(hrs_all, f["rms"], color=INK2, linewidth=0.8)
        ax_sig.set_ylabel("RMS")
        label = f"Test {test_id}, bearing {b}" + (f" — {failures[b]} failure at end of test" if b in failures else " — did not fail")
        ax_sig.set_title(label, loc="left")

        t = timeline[(timeline["test_id"] == test_id) & (timeline["bearing"] == b)]
        first = t["timestamp"].min()
        cal_end = hrs_all[np.searchsorted(f["timestamp"].to_numpy(), np.datetime64(first))]
        for ax in (ax_sig, ax_al):
            ax.axvspan(hrs_all[0], cal_end, color=GRID, alpha=0.6, linewidth=0)
            ts = f["timestamp"].to_numpy().astype("datetime64[s]").astype(np.int64)
            for r in np.flatnonzero(np.diff(ts) >= DIAG_RESTART_GAP_S) + 1:
                ax.axvline(hrs_all[r], color=MUTED, linewidth=0.6, linestyle=(0, (2, 2)))
        for j, m in enumerate(shown):
            tm = t[t["method"] == m].sort_values("timestamp")
            hrs = np.interp(tm["timestamp"].astype("int64"), f["timestamp"].astype("int64"), hrs_all)
            segs = _segments(hrs, tm["alarm"].to_numpy(bool), step=1 / 6)
            ax_al.broken_barh(segs, (j + 0.15, 0.7), color=style[m][0], linewidth=0)
        ax_al.set_yticks(np.arange(len(shown)) + 0.5, shown, fontsize=7, color=INK2)
        ax_al.set_ylim(0, len(shown))
        ax_al.grid(False)
    axes[-1].set_xlabel("operating hours (shutdowns > 1 h removed); shaded = calibration, dashed = restart after ≥ 8 h shutdown")
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)


def tradeoff(per_bearing: pd.DataFrame, methods: list[str], primary_seed: int, out: Path) -> None:
    style = method_style(methods)
    d = per_bearing[per_bearing["seed"].isin([-1, primary_seed])]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 3.8), sharex=True)
    for m in methods:
        rows = []
        for (param, value), g in d[d["method"] == m].groupby(["param", "value"]):
            ok, f = g[~g["failed"]], g[g["failed"]]
            rows.append((100 * ok["episodes"].sum() / ok["monitored_hours"].sum(),
                         int(f["detected"].sum()), int(f["early_half_episodes"].sum()),
                         bool(g["primary"].any())))
        r = pd.DataFrame(rows, columns=["fa", "det", "early", "primary"]).sort_values("fa")
        color, marker = style[m]
        for ax, col in ((ax1, "det"), (ax2, "early")):
            ax.plot(r["fa"], r[col], color=color, marker=marker, markersize=5, label=m)
            pr = r[r["primary"]]
            ax.plot(pr["fa"], pr[col], linestyle="none", marker=marker, markersize=10,
                    markerfacecolor="none", markeredgecolor=color, markeredgewidth=1.5)
    ax1.set_ylabel("failed bearings detected (of 3)")
    ax1.set_yticks([0, 1, 2, 3])
    ax2.set_ylabel("early-half alarm episodes on failed bearings")
    for ax in (ax1, ax2):
        ax.set_xlabel("non-failed alarm episodes per 100 monitored h")
    ax2.legend(fontsize=7, frameon=False, loc="upper left")
    fig.suptitle("Threshold sensitivity (each line = one method over its k or α grid; ringed = primary setting)",
                 fontsize=9, color=INK2)
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)


def validity(validity_df: pd.DataFrame, methods: list[str], primary_seed: int, out: Path) -> None:
    style = method_style(methods)
    v = validity_df[(validity_df["seed"] == primary_seed) & (~validity_df["failed"])]
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6), sharey=True)
    for ax, col, title in ((axes[0], "exceed_rate_near", "first 48 scored snapshots after calibration"),
                           (axes[1], "exceed_rate_early_half", "first half of monitored time")):
        alphas = sorted(v["alpha"].unique())
        ax.plot([0, max(alphas) * 1.1], [0, max(alphas) * 1.1], color=MUTED, linestyle=(0, (3, 3)),
                linewidth=1, label="nominal (observed = α)")
        for j, m in enumerate(v["method"].unique()):
            color, marker = style[m]
            g = v[v["method"] == m].groupby("alpha")[col]
            x = np.array(alphas) * (1 + 0.06 * (j - 0.5))
            ax.errorbar(x, g.mean().reindex(alphas), yerr=[g.mean().reindex(alphas) - g.min().reindex(alphas),
                        g.max().reindex(alphas) - g.mean().reindex(alphas)],
                        color=color, marker=marker, markersize=6, capsize=3, linewidth=1.2, label=m)
        ax.set_title(title, loc="left")
        ax.set_xlabel("nominal α")
    axes[0].set_ylabel("observed per-snapshot exceedance rate\n(non-failed bearings: mean, min–max)")
    axes[1].legend(fontsize=7, frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)


ENV_FOR_FAILURE = {"inner race": "env_bpfi", "outer race": "env_bpfo", "roller element": "env_bsf"}


def envelope_failed(features_by_test: dict[int, pd.DataFrame], failures: dict[int, dict[int, str]],
                    out: Path, max_gap_s: float, window: int = 12) -> None:
    cases = [(t, b, mode) for t in sorted(failures) for b, mode in sorted(failures[t].items())]
    fig, axes = plt.subplots(1, len(cases), figsize=(3.6 * len(cases), 3.2), squeeze=False)
    for ax, (t, b, mode) in zip(axes[0], cases):
        f = features_by_test[t]
        f = f[f["bearing"] == b].sort_values("timestamp")
        hrs = operating_hours(f["timestamp"].to_numpy(), max_gap_s)
        target = ENV_FOR_FAILURE[mode]
        others = iter([(0, (4, 2)), (0, (1, 1.5))])  # dashed / dotted: identity without color
        for col in ("env_bpfo", "env_bpfi", "env_bsf"):
            smooth = f[col].rolling(window, min_periods=1).median()  # trailing: no future samples
            if col == target:
                ax.plot(hrs, smooth, color=SERIES[0], linewidth=2, label=f"{col} (matches failure)")
            else:
                ax.plot(hrs, smooth, color=INK2, linewidth=1, linestyle=next(others), label=col)
        ax.set_title(f"T{t}B{b}: {mode}", loc="left")
        ax.set_xlabel("operating hours")
        ax.legend(fontsize=7, frameon=False, loc="upper left")
    axes[0][0].set_ylabel(f"envelope SNR (trailing median, {window} snapshots)")
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)
