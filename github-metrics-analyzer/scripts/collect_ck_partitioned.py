"""Phase S3-fix — CK OO metrics for one repo via per-module partitioning.

CK 0.7.0 parses an entire repository in a single ASTParser batch, so ONE
unresolvable file aborts the whole run with a JDT NullPointerException
(`TypeBinding.kind() ... receiverType is null`) and the repository ends up with
zero records. Observed on:
  - NationalSecurityAgency/ghidra (corpus 1)
  - thingsboard/thingsboard      (corpus 2) — triggered by a Java 14+ switch
    expression that the bundled JDT cannot resolve.

Fix (no methodology change — same CK tool, same metrics, same file-level
aggregation as collect_ck_metrics): run CK once per module source root
(`**/src/main/java`, `**/src/test/java`). A crash then loses only that one
module; every other module's metrics are still collected. Results are
aggregated to file level (relative to the repo root, so paths join with the
rest of the dataset) and written back into data/ck_metrics.csv, replacing any
existing rows for that repository.

Resumable: each source root's aggregated rows are cached under
data/partial/ck_<repo>/<sanitised-root>.csv and skipped on re-run.
Roots where CK crashed are recorded and reported — their files are simply
absent from CK (NOT fabricated as zeros), per the study rule that a
non-collectable metric is never estimated.

This generalises scripts/collect_ck_ghidra.py, which hardcoded ghidra.

Usage:
    python scripts/collect_ck_partitioned.py --repo thingsboard/thingsboard
    python scripts/collect_ck_partitioned.py --repo thingsboard/thingsboard --force
"""
from __future__ import annotations

import argparse
import csv
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd

import collect_ck_metrics as ck
from common import DATA_DIR, REPOS_DIR, ROOT, get_logger, repo_to_folder

log = get_logger("ck-partitioned")


def source_roots(repo_dir: Path) -> list[Path]:
    """Module source roots; falls back to the repo itself if none are found."""
    roots: set[Path] = set()
    for pat in ("**/src/main/java", "**/src/test/java"):
        for d in repo_dir.glob(pat):
            if d.is_dir():
                roots.add(d)
    return sorted(roots) if roots else [repo_dir]


def run_root(repo_name: str, repo_dir: Path, root: Path,
             work_dir: Path) -> tuple[list[dict], bool]:
    """Run CK on one source root. Return (file_rows, ok)."""
    sani = _sanitise(repo_dir, root)
    out_dir = work_dir / sani
    out_dir.mkdir(parents=True, exist_ok=True)
    out_prefix = out_dir.as_posix().rstrip("/") + "/"
    cmd = (
        f'java -jar "{ck.CK_JAR.as_posix()}" "{root.as_posix()}" '
        f'false 0 true "{out_prefix}"'
    )
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            encoding="utf-8", errors="ignore", timeout=900,
        )
    except subprocess.TimeoutExpired:
        log.warning("CK timed out on root %s", sani)
        return [], False
    except Exception as exc:  # noqa: BLE001
        log.warning("CK failed on root %s: %s", sani, exc)
        return [], False

    class_csv = out_dir / "class.csv"
    if not class_csv.exists():
        if result.returncode != 0:
            log.warning("CK non-zero on root %s (no class.csv)", sani)
        return [], False

    # Aggregate relative to the REPO ROOT so file paths join with the rest of
    # the dataset (CK writes absolute paths in class.csv).
    return ck._aggregate_class_csv(repo_name, class_csv, repo_dir), True


def _sanitise(repo_dir: Path, root: Path) -> str:
    if root == repo_dir:
        return "__repo_root__"
    return root.relative_to(repo_dir).as_posix().replace("/", "__")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collect CK metrics for one repo, partitioned by module.")
    parser.add_argument("--repo", required=True,
                        help="owner/name, e.g. thingsboard/thingsboard")
    parser.add_argument("--force", action="store_true",
                        help="discard cached partials and rescan every root")
    args = parser.parse_args()

    repo_name = args.repo.strip()
    folder = repo_to_folder(repo_name)
    repo_dir = REPOS_DIR / folder
    if not repo_dir.is_dir():
        log.error("Repository not cloned: %s", repo_dir)
        sys.exit(1)

    if not ck.ensure_ck_jar():
        log.error("CK JAR unavailable; cannot collect CK for %s.", repo_name)
        sys.exit(1)

    partial_dir = DATA_DIR / "partial" / f"ck_{folder}"
    work_dir = ROOT / "tools" / f"ck_tmp_{folder}"
    if args.force and partial_dir.exists():
        shutil.rmtree(partial_dir)
    partial_dir.mkdir(parents=True, exist_ok=True)

    roots = source_roots(repo_dir)
    log.info("%s: %d module source roots to scan", repo_name, len(roots))

    failed_roots: list[str] = []
    for i, root in enumerate(roots, 1):
        sani = _sanitise(repo_dir, root)
        pfile = partial_dir / f"{sani}.csv"
        if pfile.exists():
            continue
        rows, ok = run_root(repo_name, repo_dir, root, work_dir)
        if not ok:
            failed_roots.append(sani)
        # Write the partial even when empty so the root is not retried forever.
        tmp = pfile.with_suffix(".tmp")
        with open(tmp, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=ck.FIELDS, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        tmp.replace(pfile)
        if i % 20 == 0 or not ok:
            log.info("  [%d/%d] %s -> %d files%s", i, len(roots), sani,
                     len(rows), "  (CK CRASH)" if not ok else "")

    frames = []
    for pf in sorted(partial_dir.glob("*.csv")):
        try:
            d = pd.read_csv(pf, low_memory=False)
            if len(d):
                frames.append(d)
        except Exception:  # noqa: BLE001
            pass
    repo_rows = (pd.concat(frames, ignore_index=True) if frames
                 else pd.DataFrame(columns=ck.FIELDS))
    log.info("%s CK: %d files across %d roots (%d roots failed)",
             repo_name, len(repo_rows), len(roots), len(failed_roots))

    out = DATA_DIR / "ck_metrics.csv"
    if out.exists():
        existing = pd.read_csv(out, low_memory=False)
        existing = existing[existing["repository"] != repo_name]
    else:
        existing = pd.DataFrame(columns=ck.FIELDS)
    combined = pd.concat([existing, repo_rows], ignore_index=True)
    combined.to_csv(out, index=False)
    log.info("Wrote %s: %d total rows (%d repos)",
             out.name, len(combined), combined["repository"].nunique())

    if failed_roots:
        log.warning("Failed roots (files absent from CK, not fabricated): %s",
                    ", ".join(failed_roots[:30])
                    + (" ..." if len(failed_roots) > 30 else ""))


if __name__ == "__main__":
    main()
