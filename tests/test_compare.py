import pandas as pd

from bearingguard.experiments.compare import summarize, to_markdown


def sensitivity_rows(lead_failed, alarmed_ok):
    base = {"k_sigma": 3.0, "detector": "rms", "early_half_episodes": 0,
            "restart_triggered_episodes": 1, "blind_fraction": 0.1}
    rows = [{**base, "test_id": 1, "bearing": 3, "failed": True, "episodes": 1,
             "alarm_fraction": 0.5, "first_alarm_lead_h": lead_failed}]
    for b, alarmed in zip((1, 2), alarmed_ok):
        rows.append({**base, "test_id": 1, "bearing": b, "failed": False,
                     "episodes": int(alarmed), "alarm_fraction": 0.2 if alarmed else 0.0,
                     "first_alarm_lead_h": float("nan")})
    return pd.DataFrame(rows)


def test_summary_reads_values_from_runs():
    out = summarize({"a": sensitivity_rows(12.0, (True, False))}, k=3.0).iloc[0]
    assert out["lead_h (T1B3 / T1B4 / T2B1)"] == "12"
    assert out["non-failed alarmed"] == "1/2"
    assert out["non-failed time in alarm"] == "10.0%"
    assert out["restart-triggered eps"] == 3
    assert out["blind"] == "10.0%"


def test_missing_lead_time_rendered_as_dash():
    out = summarize({"a": sensitivity_rows(float("nan"), (False, False))}, k=3.0)
    assert out.iloc[0]["lead_h (T1B3 / T1B4 / T2B1)"] == "-"


def test_markdown_has_header_separator_and_rows():
    md = to_markdown(summarize({"a": sensitivity_rows(1.0, (False, False))}, k=3.0))
    lines = md.splitlines()
    assert lines[1].startswith("|---") and len(lines) == 3
