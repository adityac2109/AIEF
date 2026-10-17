import pandas as pd

from bearingguard.reporting import figures, tables


def per_bearing():
    rows = []
    for method, value, seed, primary in [("z", 3.0, -1, True), ("z", 4.0, -1, False),
                                         ("if", 3.0, 0, True), ("if", 3.0, 1, False)]:
        for (t, b, failed, det, eps, hours) in [(1, 3, True, True, 2, 300.0), (2, 1, True, False, 1, 140.0),
                                                (1, 1, False, False, 3, 300.0), (2, 2, False, False, 0, 140.0)]:
            rows.append({"method": method, "param": "k", "value": value, "seed": seed, "primary": primary,
                         "test_id": t, "bearing": b, "failed": failed, "detected": det,
                         "episodes": eps, "monitored_hours": hours, "alarm_fraction": 0.1 * eps,
                         "first_alarm_lead_h": 50.0 if eps else float("nan"),
                         "early_half_episodes": 1, "restart_triggered_episodes": 0, "blind_fraction": 0.05})
    return pd.DataFrame(rows)


def test_primary_table_pools_false_alarm_rate_over_hours():
    row = tables.primary_table(per_bearing()).set_index("method").loc["z"]
    assert row["failed detected"] == "1/2"
    assert row["non-failed eps / 100 h"] == f"{100 * 3 / 440:.2f}"
    assert row["non-failed alarmed"] == "1/2"
    assert row["lead h"] == "50 / 50"


def test_sensitivity_table_keeps_only_primary_seed():
    t = tables.sensitivity_table(per_bearing(), primary_seed=0)
    assert set(zip(t["method"], t["setting"])) == {("z", "k=3"), ("z", "k=4"), ("if", "k=3")}


def test_seed_table_reports_range():
    t = tables.seed_table(per_bearing(), primary_k=3.0, primary_alpha=0.05)
    assert t.set_index("method").loc["if", "seeds"] == 2


def test_per_bearing_table_marks_detection():
    t = tables.per_bearing_table(per_bearing()).set_index("bearing")
    assert t.loc["T1B3 (failed)", "z"].startswith("D 50h")
    assert t.loc["T2B1 (failed)", "z"].startswith("- 50h")


def test_figures_render(tmp_path):
    pb = per_bearing()
    figures.tradeoff(pb, ["z", "if"], primary_seed=0, out=tmp_path / "t.png")
    v = pd.DataFrame({"method": "if", "alpha": [0.05, 0.1], "seed": 0, "failed": False,
                      "exceed_rate_near": [0.04, 0.08], "exceed_rate_early_half": [0.1, 0.2]})
    figures.validity(v, ["z", "if"], primary_seed=0, out=tmp_path / "v.png")
    assert (tmp_path / "t.png").stat().st_size > 0 and (tmp_path / "v.png").stat().st_size > 0


def test_method_style_follows_config_order_not_rank():
    a = figures.method_style(["a", "b", "c"])
    b = figures.method_style(["a", "b"])
    assert a["a"] == b["a"] and a["b"] == b["b"]
