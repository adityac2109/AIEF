"""Summarize several threshold runs side by side as Markdown tables.

Usage:
    python -m bearingguard.experiments.compare RUN [RUN ...] [--k 3.0] [--out FILE]

RUN is a run directory written by threshold_baseline (e.g. runs/threshold_baseline_v1).
All numbers in the output are read from the runs' sensitivity.csv files.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def _fmt(x: float, digits: int = 0) -> str:
    return "-" if pd.isna(x) else f"{x:.{digits}f}"


def summarize(runs: dict[str, pd.DataFrame], k: float) -> pd.DataFrame:
    """One row per (run, detector) at the given k."""
    rows = []
    for name, s in runs.items():
        s = s[s["k_sigma"] == k]
        for det, g in s.groupby("detector", sort=False):
            failed = g[g["failed"]].sort_values(["test_id", "bearing"])
            ok = g[~g["failed"]]
            rows.append({
                "run": name,
                "detector": det,
                "lead_h (T1B3 / T1B4 / T2B1)": " / ".join(_fmt(v) for v in failed["first_alarm_lead_h"]),
                "early-half eps, failed": " / ".join(str(v) for v in failed["early_half_episodes"]),
                "non-failed alarmed": f"{(ok['episodes'] > 0).sum()}/{len(ok)}",
                "non-failed time in alarm": _fmt(ok["alarm_fraction"].mean() * 100, 1) + "%",
                "restart-triggered eps": int(g["restart_triggered_episodes"].sum()),
                "blind": _fmt(g["blind_fraction"].mean() * 100, 1) + "%",
            })
    return pd.DataFrame(rows)


def to_markdown(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(str(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join(lines)


def provenance(run_dirs: list[Path]) -> str:
    lines = ["| run | config | git commit | dirty |", "|---|---|---|---|"]
    for d in run_dirs:
        meta = json.loads((d / "metadata.json").read_text())
        lines.append(f"| {d.name} | {meta['experiment']} | `{meta['git_commit'][:7]}` | {meta['git_dirty']} |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("runs", nargs="+", type=Path)
    parser.add_argument("--k", type=float, default=3.0)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)

    runs = {d.name: pd.read_csv(d / "sensitivity.csv") for d in args.runs}
    ks = sorted(set.intersection(*(set(s["k_sigma"]) for s in runs.values())))
    if args.k not in ks:
        raise ValueError(f"k={args.k} not in every run; available: {ks}")

    parts = [f"### Summary at k = {args.k:g}", to_markdown(summarize(runs, args.k))]
    for k in ks:
        if k != args.k:
            parts += [f"### k = {k:g}", to_markdown(summarize(runs, k))]
    parts += ["### Provenance", provenance(args.runs)]
    text = "\n\n".join(parts) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
