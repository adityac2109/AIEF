"""Summary tables computed from a detect run (per_bearing.csv, validity.csv).

Aggregate false-alarm rates pool episodes and monitored hours over the
non-failed bearings (sum of episodes / sum of hours), so long runs weigh more
than short ones. Failed-bearing metrics are listed per bearing, never averaged:
with three failures an average would hide the cases.
"""

from __future__ import annotations

import pandas as pd


def _fmt(x, digits: int = 0) -> str:
    return "-" if pd.isna(x) else f"{x:.{digits}f}"


def _failed_label(g: pd.DataFrame) -> str:
    return " / ".join(f"T{t}B{b}" for t, b in zip(g["test_id"], g["bearing"]))


def summarize_setting(g: pd.DataFrame) -> dict:
    """Metrics for one method at one threshold setting and seed."""
    failed = g[g["failed"]].sort_values(["test_id", "bearing"])
    ok = g[~g["failed"]]
    return {
        "failed detected": f"{int(failed['detected'].sum())}/{len(failed)}",
        "lead h": " / ".join(_fmt(v) for v in failed["first_alarm_lead_h"]),
        "early-half eps (failed)": " / ".join(str(int(v)) for v in failed["early_half_episodes"]),
        "non-failed alarmed": f"{int((ok['episodes'] > 0).sum())}/{len(ok)}",
        "non-failed eps / 100 h": _fmt(100 * ok["episodes"].sum() / ok["monitored_hours"].sum(), 2),
        "non-failed time in alarm": _fmt(100 * ok["alarm_fraction"].mean(), 1) + "%",
        "restart-triggered eps": int(g["restart_triggered_episodes"].sum()),
        "blind": _fmt(100 * g["blind_fraction"].mean(), 1) + "%",
    }


def primary_table(per_bearing: pd.DataFrame) -> pd.DataFrame:
    p = per_bearing[per_bearing["primary"]]
    rows = [{"method": m, **summarize_setting(g)} for m, g in p.groupby("method", sort=False)]
    return pd.DataFrame(rows)


def sensitivity_table(per_bearing: pd.DataFrame, primary_seed: int) -> pd.DataFrame:
    d = per_bearing[per_bearing["seed"].isin([-1, primary_seed])]
    rows = []
    for (m, param, value), g in d.groupby(["method", "param", "value"], sort=False):
        rows.append({"method": m, "setting": f"{param}={value:g}", **summarize_setting(g)})
    return pd.DataFrame(rows)


def seed_table(per_bearing: pd.DataFrame, primary_k: float, primary_alpha: float) -> pd.DataFrame:
    d = per_bearing[per_bearing["seed"] >= 0]
    d = d[((d["param"] == "k") & (d["value"] == primary_k)) |
          ((d["param"] == "alpha") & (d["value"] == primary_alpha))]
    per_seed = []
    for (m, s), g in d.groupby(["method", "seed"], sort=False):
        f, ok = g[g["failed"]], g[~g["failed"]]
        per_seed.append({
            "method": m, "seed": s,
            "detected": int(f["detected"].sum()),
            "early": int(f["early_half_episodes"].sum()),
            "fa": 100 * ok["episodes"].sum() / ok["monitored_hours"].sum(),
            "tia": 100 * ok["alarm_fraction"].mean(),
        })
    ps = pd.DataFrame(per_seed)
    rows = []
    for m, g in ps.groupby("method", sort=False):
        rows.append({
            "method": m, "seeds": len(g),
            "failed detected (min-max)": f"{g['detected'].min()}-{g['detected'].max()}",
            "early-half eps on failed (min-max)": f"{g['early'].min()}-{g['early'].max()}",
            "non-failed eps / 100 h (min-max)": f"{g['fa'].min():.2f}-{g['fa'].max():.2f}",
            "non-failed time in alarm (min-max)": f"{g['tia'].min():.1f}-{g['tia'].max():.1f}%",
        })
    return pd.DataFrame(rows)


def validity_table(validity: pd.DataFrame, primary_seed: int) -> pd.DataFrame:
    v = validity[validity["seed"] == primary_seed]
    rows = []
    for (m, a), g in v.groupby(["method", "alpha"], sort=False):
        ok = g[~g["failed"]]
        rows.append({
            "method": m, "alpha": f"{a:g}",
            "near calibration, mean (max)": f"{ok['exceed_rate_near'].mean():.3f} ({ok['exceed_rate_near'].max():.3f})",
            "early half, mean (max)": f"{ok['exceed_rate_early_half'].mean():.3f} ({ok['exceed_rate_early_half'].max():.3f})",
            "whole run, mean (max)": f"{ok['exceed_rate_all'].mean():.3f} ({ok['exceed_rate_all'].max():.3f})",
        })
    return pd.DataFrame(rows)


def per_bearing_table(per_bearing: pd.DataFrame) -> pd.DataFrame:
    p = per_bearing[per_bearing["primary"]].copy()
    p["bearing"] = "T" + p["test_id"].astype(str) + "B" + p["bearing"].astype(str) + \
        p["failed"].map({True: " (failed)", False: ""})
    p["cell"] = [
        f"{'D' if d else '-'} {_fmt(l)}h / {e} eps / {100 * a:.0f}%" if f else f"{e} eps / {100 * a:.0f}%"
        for d, l, e, a, f in zip(p["detected"], p["first_alarm_lead_h"], p["episodes"],
                                 p["alarm_fraction"], p["failed"])
    ]
    return p.pivot(index="bearing", columns="method", values="cell")[
        list(dict.fromkeys(p["method"]))].reset_index()


def to_markdown(df: pd.DataFrame) -> str:
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(str(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join(lines)
