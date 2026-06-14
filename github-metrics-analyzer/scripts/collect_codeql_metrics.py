"""Phase S1b - Security findings via CodeQL (SAST, source-only, no build).

Second SAST source for the ML target. CodeQL extracts Java in
``--build-mode=none`` (no compilation needed) and is generally deeper than
Semgrep. The dataset target is the UNION of Semgrep and CodeQL findings
(a file is risky if EITHER tool flags it) — see build_security_dataset.py.
This file must NOT be used as a feature (anti-leakage); only as the label.

Pipeline per repo (all static, no project build):
  1. codeql database create <db> --language=java --build-mode=none --source-root=<repo>
  2. codeql database analyze  <db> <suite> --format=sarifv2.1.0 --output=<sarif>
  3. parse SARIF → one row per finding per file

Default query suite: java-security-extended (security-focused, CWE-tagged).
Override with the CODEQL_SUITE env var.

The CodeQL CLI is a heavy external binary (not pip). It is resolved via the
CODEQL_CLI env var, PATH, or E:\\developer-tools\\codeql (see common.find_external_tool).
If CodeQL is not installed, this phase logs a warning and writes an empty
findings file so the rest of the pipeline still runs (target falls back to
Semgrep only).

Output:
  data/codeql_findings.csv — columns: repository, file, rule_id, severity, cwe, message
"""
from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
from pathlib import Path

from common import (DATA_DIR, TMP_DIR, find_external_tool, folder_to_repo,
                    get_logger, iter_repo_dirs, repo_to_folder)

log = get_logger("codeql")

FIELDS = ["repository", "file", "rule_id", "severity", "cwe", "message"]

# Security-focused suite shipped with the CodeQL Java pack. "extended" widens
# recall vs the default suite — appropriate since security false-negatives are
# the worst error in this study (see ML §8.4).
SUITE = os.getenv("CODEQL_SUITE", "java-security-extended.qls")

_CODEQL = find_external_tool("CODEQL_CLI", ("codeql", "codeql.exe"),
                             subdirs=("codeql",))


def _run(cmd: list[str], timeout: int) -> subprocess.CompletedProcess | None:
    log.info("  $ %s", " ".join(cmd))
    try:
        return subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="ignore", timeout=timeout)
    except subprocess.TimeoutExpired:
        log.warning("  timed out after %ss", timeout)
    except Exception as exc:  # noqa: BLE001 - keep the pipeline alive
        log.warning("  command failed: %s", exc)
    return None


def analyze_repo(repo: Path) -> list[dict]:
    """Create a CodeQL DB (build-mode none) and run the security suite."""
    name = folder_to_repo(repo.name)
    db_dir = TMP_DIR / f"codeql_db_{repo_to_folder(name)}"
    sarif = TMP_DIR / f"codeql_{repo_to_folder(name)}.sarif"

    # Fresh DB each run (idempotent); CodeQL refuses to overwrite a non-empty dir.
    if db_dir.exists():
        shutil.rmtree(db_dir, ignore_errors=True)

    log.info("CodeQL: creating database for %s ...", name)
    created = _run(
        [_CODEQL, "database", "create", str(db_dir),
         "--language=java", "--build-mode=none",
         f"--source-root={repo}", "--overwrite"],
        timeout=3600,
    )
    if created is None or created.returncode != 0:
        log.warning("CodeQL DB creation failed for %s (stderr: %s)",
                    name, (created.stderr[:300] if created else "n/a"))
        return []

    log.info("CodeQL: analysing %s with %s ...", name, SUITE)
    analysed = _run(
        [_CODEQL, "database", "analyze", str(db_dir), f"java-queries:codeql-suites/{SUITE}",
         "--format=sarifv2.1.0", f"--output={sarif}", "--rerun"],
        timeout=3600,
    )
    # Some CLI versions take the suite without the pack prefix; retry once.
    if analysed is None or analysed.returncode != 0:
        analysed = _run(
            [_CODEQL, "database", "analyze", str(db_dir), SUITE,
             "--format=sarifv2.1.0", f"--output={sarif}", "--rerun"],
            timeout=3600,
        )
    if analysed is None or analysed.returncode != 0:
        log.warning("CodeQL analyze failed for %s (stderr: %s)",
                    name, (analysed.stderr[:300] if analysed else "n/a"))
        return []

    rows = _parse_sarif(sarif, name)
    log.info("  %d findings in %s", len(rows), name)
    # Clean up the (potentially large) DB; keep SARIF for audit under .tmp.
    shutil.rmtree(db_dir, ignore_errors=True)
    return rows


def _rule_lookup(run: dict) -> dict[str, dict]:
    """Map rule_id → {cwe, severity} from a SARIF run's rule metadata."""
    meta: dict[str, dict] = {}
    for rule in run.get("tool", {}).get("driver", {}).get("rules", []):
        props = rule.get("properties", {}) or {}
        tags = props.get("tags", []) or []
        cwes = [t.split("/")[-1].upper() for t in tags if "cwe" in t.lower()]
        sev = props.get("problem.severity") \
            or rule.get("defaultConfiguration", {}).get("level", "")
        meta[rule.get("id", "")] = {"cwe": "; ".join(cwes),
                                    "severity": str(sev).upper()}
    return meta


def _result_rows(result: dict, name: str, rule_meta: dict[str, dict]) -> list[dict]:
    rid = result.get("ruleId", "")
    msg = (result.get("message", {}) or {}).get("text", "")[:500]
    meta = rule_meta.get(rid, {})
    severity = meta.get("severity") or str(result.get("level", "")).upper()
    rows: list[dict] = []
    for loc in result.get("locations", []) or [{}]:
        phys = loc.get("physicalLocation", {}) or {}
        uri = (phys.get("artifactLocation", {}) or {}).get("uri", "")
        if not uri:
            continue
        rows.append({
            "repository": name,
            "file": uri.replace("\\", "/").lstrip("./"),
            "rule_id": rid,
            "severity": severity,
            "cwe": meta.get("cwe", ""),
            "message": msg,
        })
    return rows


def _parse_sarif(sarif: Path, name: str) -> list[dict]:
    if not sarif.exists():
        return []
    try:
        data = json.loads(sarif.read_text(encoding="utf-8", errors="ignore"))
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("SARIF parse error for %s: %s", name, exc)
        return []

    rows: list[dict] = []
    for run in data.get("runs", []):
        rule_meta = _rule_lookup(run)
        for result in run.get("results", []):
            rows.extend(_result_rows(result, name, rule_meta))
    return rows


def main() -> None:
    out = DATA_DIR / "codeql_findings.csv"

    if not _CODEQL:
        log.warning("CodeQL CLI not found (set CODEQL_CLI, add to PATH, or install "
                    "to E:\\developer-tools\\codeql). Writing empty findings; "
                    "target will fall back to Semgrep only.")
        with open(out, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=FIELDS).writeheader()
        return

    log.info("Using CodeQL CLI: %s", _CODEQL)
    all_rows: list[dict] = []
    for repo in iter_repo_dirs():
        try:
            all_rows.extend(analyze_repo(repo))
        except Exception as exc:  # noqa: BLE001
            log.warning("CodeQL phase failed for %s: %s", repo.name, exc)

    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(all_rows)
    log.info("Wrote %d finding rows to %s", len(all_rows), out.name)

    if all_rows:
        from collections import Counter
        files = len({(r["repository"], r["file"]) for r in all_rows})
        sev = Counter(r["severity"] for r in all_rows)
        log.info("Files with CodeQL findings: %d  |  Severity: %s",
                 files, dict(sev))


if __name__ == "__main__":
    main()
