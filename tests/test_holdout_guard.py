"""Guards that keep IMS test 3 sealed until the frozen holdout run."""

import subprocess
import tomllib
from pathlib import Path

import pytest

from bearingguard.data.ims import TESTS
from bearingguard.experiments import holdout

ROOT = Path(__file__).resolve().parents[1]
SEALED = {t for t, s in TESTS.items() if s.sealed}


def test_no_committed_config_reads_a_sealed_test():
    for path in (ROOT / "configs").rglob("*.toml"):
        tests = set(tomllib.loads(path.read_text()).get("tests", []))
        assert not tests & SEALED, f"{path} lists sealed test(s) {tests & SEALED}"


def fake_git(responses):
    def _git(*args):
        key = args[0] if args[0] != "rev-parse" else ("rev-parse", args[1])
        rc, out = responses.get(key, (0, ""))
        return subprocess.CompletedProcess(args, rc, stdout=out, stderr="")
    return _git


@pytest.mark.parametrize("responses, message", [
    ({("rev-parse", "--verify"): (1, "")}, "does not exist"),
    ({"status": (0, " M src/x.py")}, "not clean"),
    ({"merge-base": (1, "")}, "does not descend"),
    ({"diff": (1, "")}, "changed since"),
])
def test_freeze_check_rejects_each_violation(monkeypatch, responses, message):
    monkeypatch.setattr(holdout, "_git", fake_git(responses))
    with pytest.raises(holdout.FreezeCheckError, match=message):
        holdout.check_frozen("protocol-v1-frozen")


def test_freeze_check_passes_when_all_conditions_hold(monkeypatch):
    monkeypatch.setattr(holdout, "_git", fake_git({("rev-parse", "HEAD"): (0, "abc1234\n")}))
    assert holdout.check_frozen("protocol-v1-frozen") == "abc1234"


def test_failed_freeze_check_touches_no_data(monkeypatch):
    monkeypatch.setattr(holdout, "_git", fake_git({"status": (0, " M x")}))
    monkeypatch.setattr(holdout, "get_data_dir", lambda *_: pytest.fail("data dir was resolved"))
    with pytest.raises(holdout.FreezeCheckError):
        holdout.main(["--tag", "protocol-v1-frozen"])


def test_derived_config_changes_only_allowed_keys():
    text = (ROOT / "configs" / "protocol_v1.toml").read_text()
    base = tomllib.loads(text)
    for variant in holdout.VARIANTS:
        derived = tomllib.loads(holdout.derive_config_text(text, variant))
        changed = {k for k in base.keys() | derived.keys() if base.get(k) != derived.get(k)}
        assert changed <= {"name", "tests", "restrict_to_documented_end"}
        assert derived["tests"] == [3]
    assert tomllib.loads(holdout.derive_config_text(text, "documented"))["restrict_to_documented_end"] is True
    assert tomllib.loads(holdout.derive_config_text(text, "full_archive"))["restrict_to_documented_end"] is False


def test_derive_config_requires_every_key():
    with pytest.raises(ValueError, match="no line matching"):
        holdout.derive_config_text('name = "x"\ntests = [1]\n', "documented")


def test_reports_are_written_only_after_all_runs(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(holdout, "check_frozen", lambda tag: "abc1234")
    monkeypatch.setattr(holdout, "get_data_dir", lambda *_: tmp_path)
    monkeypatch.setattr(holdout, "validate_test", lambda *a, **k: [])
    monkeypatch.setattr(holdout, "write_manifest", lambda *a, **k: None)
    monkeypatch.setattr(holdout, "summarize", lambda *a, **k: "")

    class _Frame:
        def to_csv(self, *a, **k):
            pass

    monkeypatch.setattr(holdout, "build_features", lambda *a, **k: _Frame())
    import bearingguard.experiments.detect as detect
    import bearingguard.reporting.report as report
    monkeypatch.setattr(detect, "main", lambda argv: calls.append("run"))
    monkeypatch.setattr(report, "build_report", lambda *a, **k: calls.append("report"))

    holdout.main(["--tag", "protocol-v1-frozen", "--out-root", str(tmp_path)])

    n = len(holdout.VARIANTS)
    assert calls == ["run"] * n + ["report"] * n
