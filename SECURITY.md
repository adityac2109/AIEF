# Security and publication hygiene

## Reporting a problem

If you find a credential, personal information or restricted data in this
repository, please open a GitHub issue that says *what kind* of problem it is
and where, **without** pasting the sensitive value itself.

## What this repository does and does not contain

- **No dataset files.** The NASA IMS data is downloaded by each user from NASA
  (see `data/README.md`). Only code, summary statistics and figures derived from
  it are published.
- **No credentials.** The code needs none: the only network access is an HTTPS
  download from data.nasa.gov, verified against a recorded MD5 checksum before
  anything is extracted.
- **No machine-specific paths.** The data location comes from `--data-dir`,
  the `BEARINGGUARD_DATA_DIR` environment variable, or an untracked `.env` file
  (template: `.env.example`).

## Checks performed before publication (2026-10-17)

The current tree and every reachable commit, tag and file version were scanned for:

- credential and key formats (cloud keys, tokens, private keys, connection
  strings, authorization headers, hard-coded passwords), using `detect-secrets`
  1.5.0 and pattern rules;
- absolute local paths, email addresses and personal identifiers;
- dataset files, archives, model artifacts, logs, notebooks and environment files;
- metadata embedded in the published figures.

No credentials, private paths, personal contact details, raw data or
third-party confidential material were found in the tree or in history. The
only identity in the history is the repository owner's public GitHub username
and its GitHub no-reply address, recorded as commit author and tagger.

Changes made as a result:

- `.gitignore` covers environment files, key material, model and data formats,
  and local-only folders;
- a repeatable check, `scripts/check_repo_hygiene.py`, with an opt-in pre-commit
  hook (`scripts/hooks/pre-commit`);
- archive extraction now also verifies that no extracted file lands outside its
  target folder;
- the data directory can be set in an untracked `.env` file;
- example paths in the documentation are placeholders.

## Running the checks

```bash
python scripts/check_repo_hygiene.py            # tracked files
python scripts/check_repo_hygiene.py --staged   # what you are about to commit
python scripts/check_repo_hygiene.py --history  # all reachable history
git config core.hooksPath scripts/hooks         # run --staged before every commit
```

`ci/github-actions-ci.yml` runs the same checks plus the test suite. To enable
it, move it to `.github/workflows/ci.yml`; pushing workflow files needs a token
with the `workflow` scope.

Pattern checks catch known formats, not every possible secret. They complement
review; they do not replace it.
