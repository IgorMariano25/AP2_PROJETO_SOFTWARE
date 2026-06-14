"""Phase S5 - Secrets / credential detection via detect-secrets.

Uses the `detect-secrets` Python package (no binary required).
Scans the current working tree (HEAD) of each cloned repository.

ISO/IEC 25010 mapping:
  → Segurança > Confidencialidade (CWE-200, exposed credentials)

Output:
  data/secrets_findings.csv — one row per detected secret per file
    columns: repository, file, secret_type, line_number

  data/secrets_summary.csv — one row per repository
    columns: repository, files_with_secrets, total_secrets, types
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

from common import DATA_DIR, folder_to_repo, get_logger, iter_repo_dirs

log = get_logger("gitleaks")

_DS_CMD = Path(sys.executable).parent / "detect-secrets"
if not _DS_CMD.exists():
    _DS_CMD = "detect-secrets"

FINDING_FIELDS = ["repository", "file", "secret_type", "line_number"]
SUMMARY_FIELDS = ["repository", "files_with_secrets", "total_secrets", "types"]


def scan_repo(repo: Path) -> list[dict]:
    """Run detect-secrets scan on *repo*; return list of finding dicts."""
    name = folder_to_repo(repo.name)
    log.info("detect-secrets scanning %s ...", name)

    cmd = f'"{_DS_CMD}" scan --all-files "{repo}"'
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True,
            text=True, encoding="utf-8", errors="ignore", timeout=600,
        )
    except subprocess.TimeoutExpired:
        log.warning("detect-secrets timed out for %s", name)
        return []
    except Exception as exc:  # noqa: BLE001
        log.warning("detect-secrets failed for %s: %s", name, exc)
        return []

    raw = result.stdout.strip()
    if not raw:
        log.warning("detect-secrets produced no output for %s (stderr: %s)",
                    name, result.stderr[:200])
        return []

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        log.warning("detect-secrets JSON parse error for %s: %s", name, exc)
        return []

    rows = []
    for file_path, secrets in data.get("results", {}).items():
        try:
            rel = Path(file_path).relative_to(repo).as_posix()
        except ValueError:
            rel = file_path

        for secret in secrets:
            rows.append({
                "repository": name,
                "file": rel,
                "secret_type": secret.get("type", ""),
                "line_number": secret.get("line_number", 0),
            })

    log.info("  %d secret occurrences in %s", len(rows), name)
    return rows


def main() -> None:
    all_findings: list[dict] = []
    summaries: list[dict] = []

    for repo in iter_repo_dirs():
        name = folder_to_repo(repo.name)
        try:
            findings = scan_repo(repo)
        except Exception as exc:  # noqa: BLE001
            log.warning("Secrets phase failed for %s: %s", repo.name, exc)
            findings = []

        all_findings.extend(findings)

        files_set = {f["file"] for f in findings}
        types = Counter(f["secret_type"] for f in findings)
        summaries.append({
            "repository": name,
            "files_with_secrets": len(files_set),
            "total_secrets": len(findings),
            "types": "; ".join(f"{t}:{c}" for t, c in types.most_common()),
        })

    _write_csv(DATA_DIR / "secrets_findings.csv", all_findings, FINDING_FIELDS)
    _write_csv(DATA_DIR / "secrets_summary.csv", summaries, SUMMARY_FIELDS)


def _write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    log.info("Wrote %d rows to %s", len(rows), path.name)


if __name__ == "__main__":
    main()
