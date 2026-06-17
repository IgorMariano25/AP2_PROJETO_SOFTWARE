"""Phase S1 - Security findings via Semgrep (SAST, source-only, no build).

This is the SOURCE OF THE ML TARGET: has_security_risk = 1 if a file has
>= 1 Semgrep security finding.  It must NOT be used as a feature — only as
the label.  See build_security_dataset.py for target construction.

Rulesets used (Java security, ISO/IEC 25010 Segurança sub-characteristics):
  p/java               — general Java security rules
  p/owasp-top-ten      — OWASP Top 10 mapped rules
  p/java-spring        — Spring-specific security rules

Output:
  data/semgrep_findings.csv — one row per finding per file
    columns: repository, file, rule_id, severity, cwe, message
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from common import DATA_DIR, REPOS_DIR, folder_to_repo, get_logger, iter_repo_dirs

log = get_logger("semgrep")

# --config auto: Semgrep automatically selects community rules for the detected
# language. Works without authentication; includes java.lang.security.audit.*
# rules with CWE tags. Documented as version 1.165.0+ behaviour.
RULESETS = ["auto"]

FIELDS = ["repository", "file", "rule_id", "severity", "cwe", "message"]

# Semgrep executable inside the venv
_SEMGREP = Path(sys.executable).parent / "semgrep"
if not _SEMGREP.exists():
    _SEMGREP = Path(sys.executable).parent / "semgrep.exe"


def _semgrep_cmd() -> str:
    if _SEMGREP.exists():
        return str(_SEMGREP)
    return "semgrep"


def run_semgrep(repo: Path) -> list[dict]:
    """Run semgrep over all Java files in *repo* and return finding rows."""
    name = folder_to_repo(repo.name)
    config_flags = " ".join(f"--config {r}" for r in RULESETS)
    cmd = (
        f'"{_semgrep_cmd()}" {config_flags} '
        f'--json --no-git-ignore --quiet '
        f'--timeout 60 --jobs 2 '
        f'"{repo}"'
    )

    log.info("Semgrep scanning %s ...", name)
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=1800,
        )
    except subprocess.TimeoutExpired:
        log.warning("Semgrep timed out for %s", name)
        return []
    except Exception as exc:  # noqa: BLE001
        log.warning("Semgrep failed for %s: %s", name, exc)
        return []

    raw = result.stdout.strip()
    if not raw:
        log.warning("Semgrep produced no output for %s (stderr: %s)",
                    name, result.stderr[:300])
        return []

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        log.warning("Semgrep JSON parse error for %s: %s", name, exc)
        return []

    rows = []
    for finding in data.get("results", []):
        file_path = finding.get("path", "")
        # Make relative to repo root
        try:
            rel = Path(file_path).relative_to(repo).as_posix()
        except ValueError:
            rel = file_path

        check_id = finding.get("check_id", "")
        extra = finding.get("extra", {})
        severity = extra.get("severity", "").upper()
        message = extra.get("message", "")[:500]

        # Extract CWE tags when present
        metadata = extra.get("metadata", {})
        cwe_list = metadata.get("cwe", [])
        if isinstance(cwe_list, str):
            cwe_list = [cwe_list]
        cwe = "; ".join(cwe_list) if cwe_list else ""

        rows.append({
            "repository": name,
            "file": rel,
            "rule_id": check_id,
            "severity": severity,
            "cwe": cwe,
            "message": message,
        })

    log.info("  %d findings in %s", len(rows), name)
    return rows


def main() -> None:
    all_rows: list[dict] = []
    for repo in iter_repo_dirs():
        try:
            all_rows.extend(run_semgrep(repo))
        except Exception as exc:  # noqa: BLE001
            log.warning("Semgrep phase failed for %s: %s", repo.name, exc)

    out = DATA_DIR / "semgrep_findings.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(all_rows)

    log.info("Wrote %d finding rows to %s", len(all_rows), out.name)

    # Quick summary
    if all_rows:
        from collections import Counter
        repos_with_findings = len({r["repository"] for r in all_rows})
        files_with_findings = len({(r["repository"], r["file"]) for r in all_rows})
        sev = Counter(r["severity"] for r in all_rows)
        log.info("Repos with findings: %d  |  Files with findings: %d",
                 repos_with_findings, files_with_findings)
        log.info("Severity breakdown: %s", dict(sev))


if __name__ == "__main__":
    main()
