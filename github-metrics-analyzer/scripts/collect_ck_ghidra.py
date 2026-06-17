"""Phase S3-fix — CK OO metrics for ghidra via per-module partitioning.

CK 0.7.0 aborts the WHOLE repo run on ghidra with a JDT NullPointerException
(`TypeBinding.kind() ... receiverType is null`) triggered by a single
unresolvable file. Running CK once over all 15k files therefore yields zero
records for ghidra.

Fix (no methodology change — same CK tool, same metrics, same file-level
aggregation as collect_ck_metrics): run CK once per module source root
(`**/src/main/java`, `**/src/test/java`). A crash then loses only that one
module; every other module's metrics are still collected. Results are
aggregated to file level (relative to the ghidra repo root, so paths join with
the rest of the dataset) and written back into data/ck_metrics.csv, replacing
any existing ghidra rows.

Resumable: each source root's aggregated rows are cached under
data/partial/ck_ghidra/<sanitised-root>.csv and skipped on re-run.
Roots where CK crashed are recorded (failed_roots) and reported — their files
are simply absent from CK (NOT fabricated as zeros).
"""
from __future__ import annotations

import csv
import subprocess
from datetime import datetime
from pathlib import Path

import pandas as pd

import collect_ck_metrics as ck
from common import DATA_DIR, REPOS_DIR, ROOT, get_logger

log = get_logger("ck-ghidra")

REPO_NAME = "NationalSecurityAgency/ghidra"
GHIDRA = REPOS_DIR / "NationalSecurityAgency__ghidra"
PARTIAL_DIR = DATA_DIR / "partial" / "ck_ghidra"
WORK_DIR = ROOT / "tools" / "ck_tmp_ghidra"
RUN_LOG = ROOT / "RUN_LOG.md"


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _runlog(msg: str) -> None:
    try:
        with open(RUN_LOG, "a", encoding="utf-8") as f:
            f.write(f"\n`{_ts()}` [ck-ghidra] {msg}")
    except Exception:  # noqa: BLE001
        pass


def _sanitise(root: Path) -> str:
    return root.relative_to(GHIDRA).as_posix().replace("/", "__")


def source_roots() -> list[Path]:
    roots: set[Path] = set()
    for pat in ("**/src/main/java", "**/src/test/java"):
        for d in GHIDRA.glob(pat):
            if d.is_dir():
                roots.add(d)
    return sorted(roots)


def run_root(root: Path) -> tuple[list[dict], bool]:
    """Run CK on one source root. Return (file_rows, ok)."""
    sani = _sanitise(root)
    out_dir = WORK_DIR / sani
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
        # CK crashed before writing output for this root
        if result.returncode != 0:
            log.warning("CK non-zero on root %s (no class.csv)", sani)
        return [], False

    # Aggregate relative to the GHIDRA REPO ROOT so file paths join with the
    # rest of the dataset (CK writes absolute paths in class.csv).
    rows = ck._aggregate_class_csv(REPO_NAME, class_csv, GHIDRA)
    return rows, True


def main() -> None:
    if not ck.ensure_ck_jar():
        log.error("CK JAR unavailable; cannot collect ghidra CK.")
        return

    PARTIAL_DIR.mkdir(parents=True, exist_ok=True)
    roots = source_roots()
    log.info("ghidra: %d module source roots to scan", len(roots))
    _runlog(f"iniciando CK particionado em ghidra: {len(roots)} raizes de modulo.")

    failed_roots: list[str] = []
    done = 0
    for i, root in enumerate(roots, 1):
        sani = _sanitise(root)
        pfile = PARTIAL_DIR / f"{sani}.csv"
        if pfile.exists():
            done += 1
            continue
        rows, ok = run_root(root)
        if not ok:
            failed_roots.append(sani)
        # Write partial (even if empty) so the root is not retried endlessly.
        tmp = pfile.with_suffix(".tmp")
        with open(tmp, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=ck.FIELDS, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        tmp.replace(pfile)
        done += 1
        if i % 20 == 0 or not ok:
            log.info("  [%d/%d] %s -> %d files%s",
                     i, len(roots), sani, len(rows),
                     "  (CK CRASH)" if not ok else "")

    # Merge all ghidra partials
    frames = []
    for pf in sorted(PARTIAL_DIR.glob("*.csv")):
        try:
            d = pd.read_csv(pf, low_memory=False)
            if len(d):
                frames.append(d)
        except Exception:  # noqa: BLE001
            pass
    ghidra_rows = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=ck.FIELDS)
    n_files = len(ghidra_rows)
    log.info("ghidra CK: %d files across %d roots (%d roots failed)",
             n_files, len(roots), len(failed_roots))

    # Replace ghidra rows in the canonical ck_metrics.csv
    out = DATA_DIR / "ck_metrics.csv"
    if out.exists():
        existing = pd.read_csv(out, low_memory=False)
        existing = existing[existing["repository"] != REPO_NAME]
    else:
        existing = pd.DataFrame(columns=ck.FIELDS)
    combined = pd.concat([existing, ghidra_rows], ignore_index=True)
    combined.to_csv(out, index=False)
    log.info("Wrote %s: %d total rows (%d repos)",
             out.name, len(combined), combined["repository"].nunique())

    _runlog(
        f"CK ghidra concluido: {n_files} arquivos; "
        f"{len(failed_roots)}/{len(roots)} raizes falharam no CK (registradas como ausentes, "
        f"nao fabricadas). ck_metrics.csv agora com {combined['repository'].nunique()} repos."
    )
    if failed_roots:
        log.warning("Failed roots (files absent from CK, not fabricated): %s",
                    ", ".join(failed_roots[:30]) + (" ..." if len(failed_roots) > 30 else ""))


if __name__ == "__main__":
    main()
