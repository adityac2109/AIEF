"""Repository hygiene checks (scripts/check_repo_hygiene.py).

Sample secrets are assembled at runtime so that no literal token, key or path
is ever stored in the repository.
"""

import importlib.util
import os
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("hygiene", ROOT / "scripts" / "check_repo_hygiene.py")
hygiene = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hygiene)


@pytest.mark.parametrize("line, rule", [
    ("token = " + "gh" + "p_" + "A1b2" * 9, "GitHub token"),
    ("AK" + "IA" + "ABCDEFGHIJKLMNOP", "AWS access key id"),
    ("-" * 5 + "BEGIN RSA PRIVATE KEY" + "-" * 5, "private key"),
    ("Account" + "Key=" + "x" * 30, "Azure connection string"),
    ("pass" + 'word = "' + "hunter2hunter2" + '"', "hard-coded credential"),
    ("C:" + "\\Users\\" + "someone\\data", "absolute user path"),
    ("/ho" + "me/someone/project", "absolute user path"),
    ("contact: person" + "@" + "university.edu", "email address"),
])
def test_content_rules_flag_samples(line, rule):
    assert rule in [why for _, why in hygiene.check_content(line.encode())]


def test_allowlist_pragma_and_allowed_domains():
    assert hygiene.check_content(b"md5 = 'abc'  # pragma: allowlist secret") == []
    assert hygiene.check_content(("a" + "@" + "example.com").encode()) == []


def test_binary_content_is_skipped():
    assert hygiene.check_content(b"\x89PNG\0\0" + b"/ho" + b"me/x/") == []


@pytest.mark.parametrize("path, flagged", [
    ("data/raw/IMS.zip", True),
    ("data/README.md", False),
    ("src/bearingguard/data/ims.py", False),
    ("src/bearingguard/models/threshold.py", False),
    ("models/forest.pkl", True),
    ("runs/protocol_v1_dev/metadata.json", True),
    (".env", True),
    (".env.example", False),
    ("notes/2004.02.12.10.32.39", True),
    ("keys/id_rsa", True),
    ("docs/results/x/figures/a.png", False),
])
def test_path_rules(path, flagged):
    assert bool(hygiene.check_path(path)) is flagged


def test_large_file_flagged():
    assert any("larger than" in f for f in hygiene.check_blob("a.txt", b"x" * (hygiene.MAX_BYTES + 1)))


def test_current_tree_passes():
    os.chdir(ROOT)
    assert hygiene.scan_tree(staged=False) == []
