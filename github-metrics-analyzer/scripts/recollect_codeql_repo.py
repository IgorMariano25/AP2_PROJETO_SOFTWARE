"""Re-run the CodeQL phase for ONE repository and patch codeql_findings.csv.

Why this exists: the CodeQL Java extractor under `--build-mode=none` can index
fewer source files than it should when the machine is under heavy concurrent
load, and it reports no error when it does. The phase then completes
"successfully" with a silently smaller finding set for that repo.

Observed on thingsboard/thingsboard: 371 findings when run alone (DB build 25
min), 61 findings when run alongside a PyDriller traversal (DB build 17 min).
Every other repo in the corpus reproduced exactly, finding for finding.

This script reuses collect_codeql_metrics.analyze_repo unchanged — same CLI,
same query suite, same SARIF parsing — and only replaces that repository's rows
in data/codeql_findings.csv.

Usage:
    python scripts/recollect_codeql_repo.py --repo thingsboard/thingsboard
    python scripts/recollect_codeql_repo.py --repo thingsboard/thingsboard --min-findings 300
"""
from __future__ import annotations

import argparse
import sys

import pandas as pd

import collect_codeql_metrics as cq
from common import DATA_DIR, REPOS_DIR, get_logger, repo_to_folder

log = get_logger("codeql-repo")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Re-run CodeQL for one repo and patch codeql_findings.csv.")
    ap.add_argument("--repo", required=True, help="owner/name")
    ap.add_argument("--min-findings", type=int, default=0,
                    help="refuse to write if fewer findings than this "
                         "(guards against another silent under-extraction)")
    args = ap.parse_args()

    repo_name = args.repo.strip()
    repo_dir = REPOS_DIR / repo_to_folder(repo_name)
    if not repo_dir.is_dir():
        log.error("Repository not cloned: %s", repo_dir)
        sys.exit(1)
    if not cq._CODEQL:
        log.error("CodeQL CLI not found.")
        sys.exit(1)

    rows = cq.analyze_repo(repo_dir)
    log.info("%s: %d findings", repo_name, len(rows))

    if len(rows) < args.min_findings:
        log.error("Only %d findings (< --min-findings %d). NOT writing; the "
                  "extractor probably under-indexed again. Re-run with the "
                  "machine idle.", len(rows), args.min_findings)
        sys.exit(2)

    out = DATA_DIR / "codeql_findings.csv"
    new = pd.DataFrame(rows)
    if out.exists():
        existing = pd.read_csv(out, low_memory=False)
        before = len(existing[existing["repository"] == repo_name])
        existing = existing[existing["repository"] != repo_name]
        log.info("Replacing %d existing rows for %s", before, repo_name)
    else:
        existing = pd.DataFrame(columns=cq.FIELDS)

    combined = pd.concat([existing, new], ignore_index=True)
    combined.to_csv(out, index=False)
    log.info("Wrote %s: %d total rows (%d repos, %d files)",
             out.name, len(combined), combined["repository"].nunique(),
             combined["file"].nunique())


if __name__ == "__main__":
    main()
