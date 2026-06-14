"""Resumable per-repo runner for the native-source feature phases.

Phases: complexity (lizard), pydriller (git process metrics). The original
scripts accumulate everything in memory and write the CSV only once at the end
(not resumable; an interruption loses all progress), and the existing CSVs were
incomplete/stale:
  - complexity.csv : only 2/10 NSA repos
  - pydriller      : only 4/10 NSA repos

This runner reuses the EXACT analysis functions from those scripts (no change
to any metric definition). For each phase it:
  * processes repos smallest-first (by Java LOC from loc.csv) so the huge
    `ghidra` repo is LAST and can't block the other nine;
  * writes one partial CSV per repo immediately (crash-safe / resumable);
  * skips repos whose partial already exists;
  * optionally SEEDS partials from valid existing NSA rows (complexity,
    pydriller) so we don't recompute work already done;
  * merges all partials into the canonical data/<phase>.csv;
  * appends a per-repo line to RUN_LOG.md.

Usage:
  python collect_native_resumable.py --phases complexity,pydriller
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime
from pathlib import Path

import pandas as pd

from common import (DATA_DIR, ROOT, folder_to_repo, get_logger,
                    iter_repo_dirs, repo_to_folder)

import collect_complexity_metrics as cmod
import collect_pydriller_metrics as pmod

log = get_logger("native")
RUN_LOG = ROOT / "RUN_LOG.md"


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _runlog(msg: str) -> None:
    try:
        with open(RUN_LOG, "a", encoding="utf-8") as f:
            f.write(f"\n`{_ts()}` [native] {msg}")
    except Exception:  # noqa: BLE001
        pass


# --- per-repo analysis adapters (reuse existing functions) ------------------ #

# phase -> (analyse_fn, fieldnames, canonical_csv, seed_from_existing)
PHASES = {
    "complexity": (cmod.analyze_repo,
                   ["repository", "file", "method", "nloc", "ccn", "tokens",
                    "parameters", "length"],
                   "complexity.csv", True),
    "pydriller": (pmod.analyze_repo,
                  pmod.FIELDS,
                  "pydriller_metrics.csv", True),
}


def _java_loc() -> dict[str, int]:
    """repo full_name -> java LOC (for smallest-first ordering)."""
    p = DATA_DIR / "loc.csv"
    if not p.exists():
        return {}
    try:
        d = pd.read_csv(p)
        col = "java_code" if "java_code" in d.columns else "code"
        return dict(zip(d["repository"], d[col]))
    except Exception:  # noqa: BLE001
        return {}


def _ordered_repos() -> list[Path]:
    loc = _java_loc()
    repos = list(iter_repo_dirs())
    return sorted(repos, key=lambda r: loc.get(folder_to_repo(r.name), 1 << 62))


def _seed_partials(phase: str, fields: list[str], canonical: str,
                   pdir: Path) -> None:
    """Split valid existing NSA rows of the canonical CSV into per-repo
    partials so we skip recomputing them. Only NSA repos that are currently
    cloned are seeded."""
    src = DATA_DIR / canonical
    if not src.exists():
        return
    try:
        df = pd.read_csv(src, low_memory=False)
    except Exception:  # noqa: BLE001
        return
    if "repository" not in df.columns or df.empty:
        return
    cloned = {folder_to_repo(r.name) for r in iter_repo_dirs()}
    for repo_name, sub in df.groupby("repository"):
        if not str(repo_name).startswith("NationalSecurityAgency/"):
            continue  # ignore legacy non-NSA rows
        if repo_name not in cloned:
            continue
        pfile = pdir / f"{repo_to_folder(repo_name)}.csv"
        if pfile.exists():
            continue
        # keep only known fields, in order
        cols = [c for c in fields if c in sub.columns]
        sub[cols].to_csv(pfile, index=False)
        log.info("[%s] seeded partial from existing data: %s (%d rows)",
                 phase, repo_name, len(sub))
        _runlog(f"{phase}: semeado de dados existentes — {repo_name} ({len(sub)} linhas).")


def run_phase(phase: str) -> None:
    fn, fields, canonical, seed = PHASES[phase]
    pdir = DATA_DIR / "partial" / phase
    pdir.mkdir(parents=True, exist_ok=True)

    if seed:
        _seed_partials(phase, fields, canonical, pdir)

    repos = _ordered_repos()
    log.info("[%s] %d repos (smallest-first)", phase, len(repos))
    _runlog(f"{phase}: iniciando — {len(repos)} repos (menor->maior).")

    for repo in repos:
        name = folder_to_repo(repo.name)
        pfile = pdir / f"{repo_to_folder(name)}.csv"
        if pfile.exists():
            log.info("[%s] skip %s (partial exists)", phase, name)
            continue
        log.info("[%s] processing %s ...", phase, name)
        start = _ts()
        try:
            rows = fn(repo)
            status = "ok"
        except Exception as exc:  # noqa: BLE001 - never let one repo kill the phase
            log.warning("[%s] FAILED %s: %s", phase, name, exc)
            rows, status = [], f"FAIL: {exc}"
        # atomic partial write (even empty, so a failed repo is recorded, not retried forever)
        tmp = pfile.with_suffix(".tmp")
        with open(tmp, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        tmp.replace(pfile)
        log.info("[%s] %s -> %d rows (%s)", phase, name, len(rows), status)
        _runlog(f"{phase}: {name} {start}->{_ts()} — {len(rows)} linhas ({status}).")

    _merge_phase(phase)


def _merge_phase(phase: str) -> None:
    fn, fields, canonical, seed = PHASES[phase]
    pdir = DATA_DIR / "partial" / phase
    frames = []
    repos_present = []
    for pf in sorted(pdir.glob("*.csv")):
        try:
            d = pd.read_csv(pf, low_memory=False)
        except Exception:  # noqa: BLE001
            continue
        if len(d):
            frames.append(d)
            repos_present.extend(d["repository"].unique().tolist())
    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=fields)
    dest = DATA_DIR / canonical
    out.to_csv(dest, index=False)
    nrepos = out["repository"].nunique() if len(out) else 0
    log.info("[%s] merged -> %s (%d rows, %d repos)", phase, canonical, len(out), nrepos)
    _runlog(f"{phase}: MERGE -> {canonical} ({len(out)} linhas, {nrepos} repos).")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phases", default="complexity,pydriller",
                    help="comma-separated subset of: complexity,pydriller")
    args = ap.parse_args()
    phases = [p.strip() for p in args.phases.split(",") if p.strip() in PHASES]
    for phase in phases:
        log.info("=" * 60)
        log.info("NATIVE PHASE: %s", phase)
        log.info("=" * 60)
        run_phase(phase)


if __name__ == "__main__":
    main()
