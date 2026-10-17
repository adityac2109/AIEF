"""Run the frozen protocol once on the sealed IMS test 3.

Usage:
    python -m bearingguard.experiments.holdout --tag protocol-v1-frozen

This is the only code path that reads test 3 signal contents. Before touching
the data it checks that:
  1. the working tree is clean;
  2. HEAD descends from the freeze tag;
  3. nothing under src/, configs/ or pyproject.toml differs between the tag
     and HEAD, so the evaluated code and protocol are exactly the frozen ones.

It then validates test 3 files, builds its features, and runs the protocol
config with tests = [3] under the two pre-registered variants in
docs/holdout_protocol.md (documented range = primary, full archive = secondary).
"""

from __future__ import annotations

import argparse
import subprocess
import tomllib
from pathlib import Path

from bearingguard.config import get_data_dir
from bearingguard.data.ims import get_spec
from bearingguard.data.validate import summarize, validate_test, write_manifest
from bearingguard.features.build import build_features, features_path, manifest_path

HOLDOUT_TEST = 3
FROZEN_PATHS = ["src", "configs", "pyproject.toml"]
VARIANTS = {
    "documented": {"restrict_to_documented_end": True},    # primary
    "full_archive": {"restrict_to_documented_end": False},  # secondary
}


class FreezeCheckError(RuntimeError):
    pass


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True)


def check_frozen(tag: str) -> str:
    """Return HEAD's commit hash if the freeze conditions hold, else raise."""
    if _git("rev-parse", "--verify", f"refs/tags/{tag}").returncode != 0:
        raise FreezeCheckError(f"freeze tag {tag!r} does not exist")
    if _git("status", "--porcelain").stdout.strip():
        raise FreezeCheckError("working tree is not clean")
    if _git("merge-base", "--is-ancestor", tag, "HEAD").returncode != 0:
        raise FreezeCheckError(f"HEAD does not descend from {tag}")
    if _git("diff", "--quiet", tag, "HEAD", "--", *FROZEN_PATHS).returncode != 0:
        raise FreezeCheckError(f"code or configs changed since {tag}: {FROZEN_PATHS}")
    return _git("rev-parse", "HEAD").stdout.strip()


def holdout_config(protocol: dict, variant: str) -> dict:
    cfg = {**protocol, **VARIANTS[variant]}
    cfg["tests"] = [HOLDOUT_TEST]
    cfg["name"] = f"holdout_v1_{variant}"
    return cfg


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", required=True, help="git tag marking the frozen protocol")
    parser.add_argument("--config", type=Path, default=Path("configs/protocol_v1.toml"))
    parser.add_argument("--data-dir", help="overrides BEARINGGUARD_DATA_DIR")
    parser.add_argument("--out-root", type=Path, default=Path("runs"))
    args = parser.parse_args(argv)

    commit = check_frozen(args.tag)
    print(f"Freeze checks passed at {commit[:7]} (tag {args.tag}). Unsealing test {HOLDOUT_TEST}.")
    data_dir = get_data_dir(args.data_dir)
    spec = get_spec(HOLDOUT_TEST, allow_sealed=True)

    records = validate_test(data_dir, HOLDOUT_TEST, allow_sealed=True)
    write_manifest(records, spec, manifest_path(data_dir, HOLDOUT_TEST))
    print(summarize(records, spec))
    for s in ("time", "spectral"):
        df = build_features(data_dir, HOLDOUT_TEST, s, allow_sealed=True)
        df.to_csv(features_path(data_dir, HOLDOUT_TEST, s), index=False)

    from bearingguard.experiments import detect
    from bearingguard.reporting.report import build_report

    protocol_text = args.config.read_text()
    for variant in VARIANTS:
        text = derive_config_text(protocol_text, variant)
        cfg_path = args.out_root / f"holdout_v1_{variant}.toml"
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(text)
        detect.main([str(cfg_path), "--allow-sealed", "--out-root", str(args.out_root),
                     *(["--data-dir", args.data_dir] if args.data_dir else [])])
        build_report(args.out_root / f"holdout_v1_{variant}",
                     Path("docs/results") / f"holdout_v1_{variant}", data_dir)
    return 0


def derive_config_text(protocol_text: str, variant: str) -> str:
    """Protocol TOML with only name, tests and the end-of-test rule replaced.

    Text substitution (rather than re-serializing) keeps every other line,
    including comments, byte-identical to the frozen file.
    """
    import re

    replacements = {
        r'^name = .*$': f'name = "holdout_v1_{variant}"',
        r'^tests = .*$': f"tests = [{HOLDOUT_TEST}]",
        r'^restrict_to_documented_end = .*$':
            f"restrict_to_documented_end = {str(VARIANTS[variant]['restrict_to_documented_end']).lower()}",
    }
    text = protocol_text
    for pattern, new in replacements.items():
        text, n = re.subn(pattern, new, text, count=1, flags=re.MULTILINE)
        if n != 1:
            raise ValueError(f"protocol config has no line matching {pattern!r}")
    header = f"# Derived from the frozen protocol for the holdout ({variant} variant).\n"
    derived = header + text
    expected = holdout_config(tomllib.loads(protocol_text), variant)
    if tomllib.loads(derived) != expected:
        raise ValueError("derived holdout config differs from the frozen protocol beyond the allowed keys")
    return derived


if __name__ == "__main__":
    raise SystemExit(main())
