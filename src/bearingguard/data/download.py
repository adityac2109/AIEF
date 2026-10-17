"""Download IMS.zip from NASA, verify it, and extract the per-test archives.

Usage:
    python -m bearingguard.data.download [--data-dir DIR]

Resulting layout under the data directory:
    raw/IMS.zip
    raw/test1/..., raw/test2/..., raw/test3/...   (extracted snapshot files)
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

from bearingguard.config import get_data_dir
from bearingguard.data.ims import TESTS, extracted_dir, list_snapshots

IMS_URL = "https://data.nasa.gov/docs/legacy/IMS.zip"
# S3 ETag of the published object (single-part upload, so it equals the MD5).
# Recorded 2026-10-16; object Last-Modified 2025-03-26, 1,061,902,801 bytes.
IMS_MD5 = "57b2e74587d73b5485fe0d55731e1331"


def md5sum(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()


def download(dest: Path) -> None:
    tmp = dest.with_suffix(".part")
    print(f"Downloading {IMS_URL} -> {dest}")
    with urllib.request.urlopen(IMS_URL) as resp, tmp.open("wb") as out:
        total = int(resp.headers.get("Content-Length", 0))
        done = 0
        while block := resp.read(1 << 20):
            out.write(block)
            done += len(block)
            if total:
                print(f"\r  {done / 1e6:,.0f} / {total / 1e6:,.0f} MB", end="", flush=True)
    print()
    tmp.replace(dest)


def find_rar_capable_tar() -> str:
    """Return a tar executable that can read RAR (bsdtar/libarchive).

    GNU tar cannot. On Windows, Git Bash puts GNU tar first on PATH, so prefer
    the bsdtar that ships with Windows 10+ in System32.
    """
    candidates = []
    if sys.platform == "win32":
        candidates.append(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "tar.exe")
    candidates += [shutil.which("bsdtar"), shutil.which("tar")]
    for exe in filter(None, candidates):
        exe = str(exe)
        if not Path(exe).exists():
            continue
        version = subprocess.run([exe, "--version"], capture_output=True, text=True).stdout
        if "bsdtar" in version or "libarchive" in version:
            return exe
    raise RuntimeError(
        "No RAR-capable tar found. Install bsdtar (libarchive) or extract the "
        ".rar files manually as described in data/README.md."
    )


def extract(zip_path: Path, raw_dir: Path) -> None:
    tar = find_rar_capable_tar()
    with zipfile.ZipFile(zip_path) as zf:
        for spec in TESTS.values():
            target = extracted_dir(raw_dir.parent, spec.test_id)
            if target.exists() and any(target.iterdir()):
                print(f"Test {spec.test_id}: already extracted at {target}")
                continue
            member = f"IMS/{spec.archive}"
            rar_path = raw_dir / spec.archive
            print(f"Test {spec.test_id}: extracting {member}")
            with zf.open(member) as src, rar_path.open("wb") as dst:
                shutil.copyfileobj(src, dst, 1 << 20)
            target.mkdir(parents=True, exist_ok=True)
            subprocess.run([tar, "-xf", str(rar_path), "-C", str(target)], check=True)
            rar_path.unlink()


def report_counts(data_dir: Path) -> None:
    # File counts only: this does not read signal values, so it is safe to run
    # on the sealed test.
    for spec in TESTS.values():
        n = len(list_snapshots(extracted_dir(data_dir, spec.test_id)))
        status = "OK" if n == spec.expected_files else "MISMATCH"
        print(f"Test {spec.test_id}: {n} files (readme: {spec.expected_files}) {status}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", help="overrides BEARINGGUARD_DATA_DIR")
    args = parser.parse_args(argv)

    data_dir = get_data_dir(args.data_dir)
    raw_dir = data_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    zip_path = raw_dir / "IMS.zip"

    if not zip_path.exists():
        download(zip_path)
    print("Verifying checksum...")
    actual = md5sum(zip_path)
    if actual != IMS_MD5:
        print(
            f"Checksum mismatch: got {actual}, expected {IMS_MD5}. The published "
            "archive may have changed; delete it and re-download, or update IMS_MD5 "
            "after inspecting the new release.",
            file=sys.stderr,
        )
        return 1

    extract(zip_path, raw_dir)
    report_counts(data_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
