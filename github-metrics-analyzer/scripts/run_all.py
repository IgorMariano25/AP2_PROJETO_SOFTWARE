"""run_all.py - Orchestrate the full pipeline in order.

Each phase is a standalone, idempotent module. Failures in one phase are logged
but do not abort the whole run (unless --strict is passed). Use --skip to skip
phases (e.g. --skip search,clone when repos are already present).

Examples:
    python scripts/run_all.py
    python scripts/run_all.py --skip search,clone
    python scripts/run_all.py --only loc,complexity,structure
"""
from __future__ import annotations

import argparse
import importlib
import sys
import time

from common import get_logger

log = get_logger("run_all")

PHASES = [
    ("search", "search_repositories"),
    ("clone", "clone_repositories"),
    ("git", "collect_git_metrics"),
    ("pr", "collect_pr_metrics"),
    ("loc", "collect_loc_metrics"),
    ("complexity", "collect_complexity_metrics"),
    ("structure", "collect_structure_metrics"),
    ("tests", "collect_test_metrics"),
    ("consolidate", "consolidate"),
    ("indicators", "compute_indicators"),
    ("report", "generate_report"),
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
