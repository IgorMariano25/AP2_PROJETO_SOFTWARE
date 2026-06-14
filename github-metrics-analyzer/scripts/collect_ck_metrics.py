"""Phase S3 - OO metrics via the CK tool (Maurício Aniche, Java, source-only).

CK computes class-level metrics: WMC, DIT, NOC, CBO, RFC, LCOM, etc.
It parses Java *source* — no bytecode required.

The CK JAR is downloaded automatically on first run to:
  github-metrics-analyzer/tools/ck.jar

CK command (see https://github.com/mauricioaniche/ck):
  java -jar ck.jar <src_dir> <use_jars:false> <max_files:0>
       <variable_and_field_metrics:true> <output_dir>

Class-level output is aggregated to FILE level (one row per .java file).
Aggregation strategy:
  - WMC, RFC           → sum (file total)
  - DIT, NOC, CBO, TCC → max (most "risky" class dominates)
  - LCOM, LCOM*        → max
  - num_methods        → sum

Output:
  data/ck_metrics.csv — one row per Java file per repository
"""
from __future__ import annotations

import csv
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

from common import DATA_DIR, ROOT, folder_to_repo, get_logger, iter_repo_dirs

log = get_logger("ck")

TOOLS_DIR = ROOT / "tools"
CK_JAR = TOOLS_DIR / "ck.jar"

# CK is not published as a GitHub release asset; its runnable "fat" jar
# (jar-with-dependencies) is hosted on Maven Central. 0.7.0 is the latest
# released version (verified 2026-06: repo1.maven.org metadata).
CK_DOWNLOAD_URL = (
    "https://repo1.maven.org/maven2/com/github/mauricioaniche/ck/"
    "0.7.0/ck-0.7.0-jar-with-dependencies.jar"
)

FIELDS = [
    "repository", "file",
    "wmc", "dit", "noc", "cbo", "rfc",
    "lcom", "lcom_star",
    "num_methods", "num_static_methods",
    "num_fields", "num_static_fields",
    "tcc", "lcc",
    "num_classes",
]


def ensure_ck_jar() -> bool:
    """Download CK JAR if not present. Returns True if available."""
    TOOLS_DIR.mkdir(parents=True, exist_ok=True)
    if CK_JAR.exists():
        return True

    log.info("Downloading CK JAR from %s ...", CK_DOWNLOAD_URL)
    try:
        import requests
        resp = requests.get(CK_DOWNLOAD_URL, timeout=120, stream=True)
        resp.raise_for_status()
        with open(CK_JAR, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                f.write(chunk)
        log.info("CK JAR downloaded to %s", CK_JAR)
        return True
    except Exception as exc:  # noqa: BLE001
        log.error("Failed to download CK JAR: %s", exc)
        log.error("Please download manually from %s and save to %s",
                  CK_DOWNLOAD_URL, CK_JAR)
        return False


def run_ck(repo: Path, tmp_dir: Path) -> list[dict]:
    """Run CK on *repo* writing outputs to *tmp_dir*; return aggregated rows."""
    name = folder_to_repo(repo.name)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    # CK writes class.csv / method.csv / field.csv / variable.csv to tmp_dir.
    # CK appends the filename directly to the 5th arg (the "output prefix"),
    # so it MUST end with a separator. Use forward slashes everywhere: Java
    # accepts them on Windows, and a trailing "/" inside quotes avoids the
    # Windows trailing-backslash-escapes-the-quote bug (`...dir\"` -> bad path).
    out_prefix = tmp_dir.as_posix().rstrip("/") + "/"
    cmd = (
        f'java -jar "{CK_JAR.as_posix()}" "{repo.as_posix()}" '
        f'false 0 true "{out_prefix}"'
    )
    log.info("CK scanning %s ...", name)
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True,
            text=True, encoding="utf-8", errors="ignore", timeout=1800,
        )
        if result.returncode != 0:
            log.warning("CK non-zero exit for %s: %s",
                        name, result.stderr[:400])
    except subprocess.TimeoutExpired:
        log.warning("CK timed out for %s", name)
        return []
    except Exception as exc:  # noqa: BLE001
        log.warning("CK failed for %s: %s", name, exc)
        return []

    class_csv = tmp_dir / "class.csv"
    if not class_csv.exists():
        log.warning("CK produced no class.csv for %s", name)
        return []

    return _aggregate_class_csv(name, class_csv, repo)


def _aggregate_class_csv(repo_name: str, class_csv: Path,
                          repo_root: Path) -> list[dict]:
    """Aggregate class-level CK output to file level."""
    # Buckets per file
    sums: defaultdict[str, dict] = defaultdict(lambda: {
        "wmc": 0, "rfc": 0, "num_methods": 0,
        "num_static_methods": 0, "num_fields": 0, "num_static_fields": 0,
        "num_classes": 0,
    })
    maxes: defaultdict[str, dict] = defaultdict(lambda: {
        "dit": 0, "noc": 0, "cbo": 0, "lcom": 0, "lcom_star": 0,
        "tcc": 0.0, "lcc": 0.0,
    })

    try:
        with open(class_csv, encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            for row in reader:
                file_path = row.get("file", "")
                try:
                    rel = Path(file_path).relative_to(repo_root).as_posix()
                except ValueError:
                    rel = file_path

                def _int(key: str) -> int:
                    try:
                        return int(row.get(key, 0) or 0)
                    except (ValueError, TypeError):
                        return 0

                def _float(key: str) -> float:
                    try:
                        return float(row.get(key, 0.0) or 0.0)
                    except (ValueError, TypeError):
                        return 0.0

                s = sums[rel]
                # CK 0.7.0 (Maven Central) column names — verified from the
                # generated class.csv header. Earlier names like
                # "totalMethodsIncludingGettersSetters" do not exist in 0.7.0.
                s["wmc"] += _int("wmc")
                s["rfc"] += _int("rfc")
                s["num_methods"] += _int("totalMethodsQty")
                s["num_static_methods"] += _int("staticMethodsQty")
                s["num_fields"] += _int("totalFieldsQty")
                s["num_static_fields"] += _int("staticFieldsQty")
                s["num_classes"] += 1

                m = maxes[rel]
                m["dit"] = max(m["dit"], _int("dit"))
                m["noc"] = max(m["noc"], _int("noc"))
                m["cbo"] = max(m["cbo"], _int("cbo"))
                m["lcom"] = max(m["lcom"], _int("lcom"))
                m["lcom_star"] = max(m["lcom_star"], _int("lcom*"))
                m["tcc"] = max(m["tcc"], _float("tcc"))
                m["lcc"] = max(m["lcc"], _float("lcc"))

    except Exception as exc:  # noqa: BLE001
        log.warning("Could not parse %s: %s", class_csv, exc)
        return []

    rows = []
    for fpath in sums:
        s = sums[fpath]
        m = maxes[fpath]
        rows.append({
            "repository": repo_name,
            "file": fpath,
            **s,
            **m,
        })
    return rows


def main() -> None:
    if not ensure_ck_jar():
        log.error("CK JAR unavailable; skipping CK metrics.")
        _write([])
        return

    all_rows: list[dict] = []
    ck_tmp = ROOT / "tools" / "ck_tmp"

    for repo in iter_repo_dirs():
        repo_tmp = ck_tmp / repo.name
        try:
            rows = run_ck(repo, repo_tmp)
            all_rows.extend(rows)
            log.info("  %d file records for %s", len(rows), repo.name)
        except Exception as exc:  # noqa: BLE001
            log.warning("CK phase failed for %s: %s", repo.name, exc)

    _write(all_rows)


def _write(rows: list[dict]) -> None:
    out = DATA_DIR / "ck_metrics.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    log.info("Wrote %d file rows to %s", len(rows), out.name)


if __name__ == "__main__":
    main()
