#!/usr/bin/env python3
"""Pre-publication hygiene check for this repository (standard library only).

Usage:
    python scripts/check_repo_hygiene.py            # tracked files (working tree)
    python scripts/check_repo_hygiene.py --staged   # files staged for commit
    python scripts/check_repo_hygiene.py --history  # every file version in reachable history

Flags raw or derived dataset files, credentials and key material, large
files, machine-specific absolute paths and email addresses. Findings report the
file, line and rule, never the matched value. Exit code 1 if anything is
found. A line containing "pragma: allowlist" is skipped (use sparingly, for
public values such as checksums).

This is a safety net, not a guarantee: pattern checks miss secrets in unknown
formats. Use a dedicated scanner (e.g. detect-secrets, gitleaks) as well.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys

MAX_BYTES = 2_000_000

FORBIDDEN_PATHS = [
    (re.compile(r"(^|/)\.env$|(^|/)\.env\.(?!example$)[^/]+$"), "environment file"),
    # Root-anchored: src/bearingguard/data/ and src/bearingguard/models/ are source packages.
    (re.compile(r"^(\.local|runs|artifacts|models)/"), "local or generated output directory"),
    (re.compile(r"^data/(?!README\.md$)"), "file under data/ (datasets live outside the repo)"),
    (re.compile(r"\.(zip|rar|7z|tar|gz|csv|parquet|npy|npz|pkl|pickle|joblib|h5|hdf5|pt|pth|onnx|sqlite|db|log)$", re.I),
     "dataset, model artifact, archive or log"),
    (re.compile(r"\.(pem|key|p12|pfx|jks|keystore|ppk)$|(^|/)id_(rsa|dsa|ecdsa|ed25519)", re.I), "key material"),
    (re.compile(r"(^|/)\d{4}\.\d{2}\.\d{2}\.\d{2}\.\d{2}\.\d{2}$"), "IMS raw snapshot file"),
]

CONTENT_RULES = [
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}"), "GitHub token"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AWS access key id"),
    (re.compile(r"xox[abprs]-[A-Za-z0-9-]{10,}"), "Slack token"),
    (re.compile(r"AIza[0-9A-Za-z_-]{35}"), "Google API key"),
    (re.compile(r"sk-[A-Za-z0-9_-]{20,}"), "API secret key"),
    (re.compile(r"-{5}BEGIN [A-Z ]*PRIVATE KEY-{5}"), "private key"),
    # "(?#)" is an empty regex comment: it keeps this source line from matching its own rule.
    (re.compile(r"AccountKey=[A-Za-z0-9+/=]{20,}|SharedAccess(?#)Signature=|DefaultEndpointsProtocol=https?;"),
     "Azure connection string"),
    (re.compile(r"(?i)\bAuthorization:\s*(Bearer|Basic)\s+[A-Za-z0-9._~+/=-]{12,}"), "authorization header"),
    (re.compile(r"(?i)\b(password|passwd|secret|api[_-]?key|access[_-]?token)\b\s*[:=]\s*['\"][^'\"\s]{8,}['\"]"),
     "hard-coded credential"),
    (re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+[A-Za-z0-9_.-]+|/home/[a-z_][a-z0-9_-]*/|/Users/[A-Za-z0-9_.-]+/"),
     "absolute user path"),
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z0-9.-]*[A-Za-z]{2,}"), "email address"),
]
ALLOWED_EMAIL_DOMAINS = ("example.com", "example.org")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", check=True).stdout


def git_bytes(*args: str) -> bytes:
    return subprocess.run(["git", *args], capture_output=True, check=True).stdout


def check_path(path: str) -> list[str]:
    if path.endswith(".env.example"):
        return []
    return [why for rx, why in FORBIDDEN_PATHS if rx.search(path)]


def check_content(data: bytes) -> list[tuple[int, str]]:
    if b"\0" in data[:8000]:  # binary (e.g. PNG figures): only path and size rules apply
        return []
    findings = []
    for n, line in enumerate(data.decode("utf-8", errors="replace").splitlines(), 1):
        if "pragma: allowlist" in line:
            continue
        for rx, why in CONTENT_RULES:
            # Cheap prefilter: the email pattern backtracks quadratically on
            # long lines without "@", so only run it where it can match.
            if why == "email address" and "@" not in line:
                continue
            for m in rx.finditer(line):
                if why == "email address" and m.group().lower().endswith(ALLOWED_EMAIL_DOMAINS):
                    continue
                findings.append((n, why))
    return findings


def check_blob(path: str, data: bytes) -> list[str]:
    out = [f"{path}: {why}" for why in check_path(path)]
    if len(data) > MAX_BYTES:
        # Already a finding; skip content rules rather than regex-scan a huge blob.
        return out + [f"{path}: larger than {MAX_BYTES // 1_000_000} MB"]
    return out + [f"{path}:{n}: {why}" for n, why in check_content(data)]


def tracked(staged: bool) -> list[str]:
    if staged:
        return [p for p in git("diff", "--cached", "--name-only", "--diff-filter=ACMR").splitlines() if p]
    return [p for p in git("ls-files").splitlines() if p]


def scan_tree(staged: bool) -> list[str]:
    findings = []
    for path in tracked(staged):
        data = git_bytes("show", f":{path}") if staged else open(path, "rb").read()
        findings += check_blob(path, data)
    return findings


def scan_history() -> list[str]:
    findings, seen = [], set()
    for line in git("rev-list", "--all", "--objects").splitlines():
        parts = line.split(maxsplit=1)
        if len(parts) != 2 or parts[0] in seen:
            continue
        sha, path = parts
        if git("cat-file", "-t", sha).strip() != "blob":
            continue
        seen.add(sha)
        findings += [f"[history {sha[:7]}] {f}" for f in check_blob(path, git_bytes("cat-file", "-p", sha))]
    messages = git("log", "--all", "--format=%B") + git("for-each-ref", "--format=%(contents)", "refs/tags")
    findings += [f"[commit/tag message] line {n}: {why}" for n, why in check_content(messages.encode())]
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--staged", action="store_true")
    mode.add_argument("--history", action="store_true")
    args = parser.parse_args(argv)

    findings = scan_history() if args.history else scan_tree(args.staged)
    scope = "history" if args.history else ("staged files" if args.staged else "tracked files")
    if findings:
        print(f"Hygiene check FAILED ({scope}): {len(findings)} finding(s)")
        for f in findings:
            print("  " + f)
        return 1
    print(f"Hygiene check passed ({scope}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
