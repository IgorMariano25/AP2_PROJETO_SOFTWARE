"""run_all.py - Orchestrate the full pipeline in order.

Each phase is a standalone, idempotent module. Failures in one phase are logged
but do not abort the whole run (unless --strict is passed). Use --skip to skip
phases (e.g. --skip clone when repos are already present).

AP2 Security pipeline phases (NSA Java repos, ISO/IEC 25010 study):
  clone      — clone/update the 10 NSA repos from repos.txt (no build)
  loc        — lines of code via cloc (fallback: Python counter) — normalisation
  complexity — cyclomatic complexity per method via lizard (feature)
  semgrep    — SAST security findings per file → ML target (Semgrep)
  pydriller  — file-level process metrics (authors, age, churn) via PyDriller (feature)
  ck         — OO metrics (WMC, DIT, CBO, LCOM …) via CK JAR (feature)
  osv        — SCA: declared CVEs from pom.xml via OSV API (descriptive)
  secrets    — credential/secret detection via detect-secrets (descriptive)
  dataset    — merge all metrics → security_dataset.csv (file-level)
  ml         — ML pipeline: GroupKFold, 5 models, SHAP, ROC charts
  report     — comparative ISO 25010 report (per-repo posture, CWE, charts)

Note: process metrics come from PyDriller (the canonical process tool), not from
a separate git-log collector — that avoids double-counting the same dimension.

Examples:
    python scripts/run_all.py --skip clone            (repos already cloned)
    python scripts/run_all.py --only semgrep,dataset,ml
    python scripts/run_all.py --only clone,complexity,semgrep,pydriller,ck,dataset,ml
"""
from __future__ import annotations

import argparse
import importlib
import sys
import time

from common import get_logger

log = get_logger("run_all")

# AP2 security study pipeline (default)
PHASES = [
    ("clone",      "clone_repositories"),
    ("loc",        "collect_loc_metrics"),
    ("complexity", "collect_complexity_metrics"),
    ("semgrep",    "collect_semgrep_metrics"),
    ("pydriller",  "collect_pydriller_metrics"),
    ("ck",         "collect_ck_metrics"),
    ("osv",        "collect_osv_metrics"),
    ("secrets",    "collect_gitleaks_metrics"),
    ("dataset",    "build_security_dataset"),
    ("ml",         "ml_security_pipeline"),
    ("report",     "generate_comparative_report"),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the MSR pipeline.")
    parser.add_argument("--skip", default="", help="comma-separated phase names to skip")
    parser.add_argument("--only", default="", help="comma-separated phase names to run")
    parser.add_argument("--strict", action="store_true", help="abort on first failure")
    args = parser.parse_args()

    skip = {s.strip() for s in args.skip.split(",") if s.strip()}
    only = {s.strip() for s in args.only.split(",") if s.strip()}

    failures = []
    for key, module_name in PHASES:
        if only and key not in only:
            continue
        if key in skip:
            log.info("Skipping phase '%s'", key)
            continue

        log.info("=" * 60)
        log.info("PHASE: %s (%s)", key, module_name)
        log.info("=" * 60)
        start = time.time()
        try:
            module = importlib.import_module(module_name)
            module.main()
            log.info("Phase '%s' finished in %.1fs", key, time.time() - start)
        except Exception as exc:  # noqa: BLE001
            log.exception("Phase '%s' failed: %s", key, exc)
            failures.append(key)
            if args.strict:
                return 1

    if failures:
        log.warning("Completed with failures in: %s", ", ".join(failures))
        return 1
    log.info("Pipeline completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
