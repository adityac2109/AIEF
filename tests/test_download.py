"""Archive extraction safety."""

from pathlib import Path

import pytest

from bearingguard.data.download import assert_within


def test_extraction_containment(tmp_path):
    root = tmp_path / "test2"
    (root / "2nd_test").mkdir(parents=True)
    (root / "2nd_test" / "2004.02.12.10.32.39").write_text("0\n")
    assert_within(root)  # inside: fine
    outside = tmp_path / "outside.txt"
    outside.write_text("x")
    link = root / "escape"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks not permitted on this system")
    with pytest.raises(RuntimeError, match="escapes"):
        assert_within(root)


def test_extraction_containment_rejects_outside_path(tmp_path, monkeypatch):
    # Platform-independent version of the symlink case: an extracted entry that
    # resolves outside the target directory must be rejected.
    root = tmp_path / "test3"
    root.mkdir()
    outside = tmp_path / "elsewhere" / "file"
    monkeypatch.setattr(Path, "rglob", lambda self, pattern: iter([outside]))
    with pytest.raises(RuntimeError, match="escapes"):
        assert_within(root)
