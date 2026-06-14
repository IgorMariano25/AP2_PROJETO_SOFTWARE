"""Phase S5 - Secrets / credential detection (Gitleaks + detect-secrets).

ISO/IEC 25010 mapping: Segurança > Confidencialidade (CWE-200, exposed creds).

Secrets are a DESCRIPTIVE dimension (study §6.6) — they are NOT ML features or
the ML target — so combining two detectors carries no leakage/multicollinearity
risk. We run both the canonical Gitleaks binary (study §5) and the Python
detect-secrets, then DEDUPLICATE the union by (file, line, normalised type).
A `detected_by` field (gitleaks / detect-secrets / both) turns the overlap into
cross-validation: agreement strengthens the finding; disagreement is reported
transparently. The headline count is the deduplicated union (no double-count).

Gitleaks is a heavy external binary (not pip), resolved via GITLEAKS_CLI, PATH,
or E:\\developer-tools\\gitleaks. If a tool is absent the phase degrades
gracefully to whichever detector is available.

Output:
  data/secrets_findings.csv — repository, file, secret_type, line_number, detected_by
  data/secrets_summary.csv  — per-repo counts + cross-validation breakdown
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

from common import (DATA_DIR, TMP_DIR, find_external_tool, folder_to_repo,
                    get_logger, iter_repo_dirs, repo_to_folder)

log = get_logger("secrets")

FINDING_FIELDS = ["repository", "file", "secret_type", "line_number", "detected_by"]
SUMMARY_FIELDS = ["repository", "files_with_secrets", "total_secrets",
                  "by_gitleaks", "by_detect_secrets", "by_both", "types"]

_GITLEAKS = find_external_tool("GITLEAKS_CLI", ("gitleaks", "gitleaks.exe"),
                               subdirs=("gitleaks",))
_DS_CMD = Path(sys.executable).parent / "detect-secrets"
if not _DS_CMD.exists():
    _DS_CMD = Path(sys.executable).parent / "detect-secrets.exe"
_DS = str(_DS_CMD) if _DS_CMD.exists() else "detect-secrets"


def _norm_type(raw: str) -> str:
    """Normalise tool-specific rule names to a coarse comparable type."""
    return "".join(c for c in raw.lower() if c.isalnum())


def _key(file: str, line: int, stype: str) -> tuple:
    return (file, int(line or 0), _norm_type(stype))


# ------------------------------------------------------------------ #
# detect-secrets (Python, current working tree)
# ------------------------------------------------------------------ #

def scan_detect_secrets(repo: Path, name: str) -> dict[tuple, dict]:
    cmd = f'"{_DS}" scan --all-files "{repo}"'
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                                encoding="utf-8", errors="ignore", timeout=600)
    except (subprocess.TimeoutExpired, OSError) as exc:
        log.warning("detect-secrets failed for %s: %s", name, exc)
        return {}
    raw = (result.stdout or "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}

    found: dict[tuple, dict] = {}
    for file_path, secrets in data.get("results", {}).items():
        rel = _relpath(file_path, repo)
        for secret in secrets:
            stype = secret.get("type", "")
            line = secret.get("line_number", 0)
            found[_key(rel, line, stype)] = {
                "repository": name, "file": rel,
                "secret_type": stype, "line_number": line,
            }
    return found


# ------------------------------------------------------------------ #
# Gitleaks (canonical binary, filesystem scan of the working tree)
# ------------------------------------------------------------------ #

def scan_gitleaks(repo: Path, name: str) -> dict[tuple, dict]:
    if not _GITLEAKS:
        return {}
    report = TMP_DIR / f"gitleaks_{repo_to_folder(name)}.json"
    # `gitleaks dir` scans the filesystem (current tree) → comparable to
    # detect-secrets. Exit code 1 just means leaks found, not an error.
    cmd = [_GITLEAKS, "dir", str(repo), "--report-format", "json",
           "--report-path", str(report), "--no-banner", "--exit-code", "0"]
    try:
        subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="ignore", timeout=1800)
    except subprocess.TimeoutExpired:
        log.warning("gitleaks timed out for %s", name)
        return {}
    except OSError:
        # Older gitleaks lacks the `dir` verb; fall back to no-git detect.
        cmd = [_GITLEAKS, "detect", "--source", str(repo), "--no-git",
               "--report-format", "json", "--report-path", str(report),
               "--no-banner", "--exit-code", "0"]
        try:
            subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="ignore", timeout=1800)
        except (subprocess.TimeoutExpired, OSError) as exc:
            log.warning("gitleaks failed for %s: %s", name, exc)
            return {}

    if not report.exists():
        return {}
    try:
        data = json.loads(report.read_text(encoding="utf-8", errors="ignore") or "[]")
    except (json.JSONDecodeError, OSError):
        return {}

    found: dict[tuple, dict] = {}
    for f in data or []:
        rel = _relpath(f.get("File", ""), repo)
        line = f.get("StartLine", 0)
        stype = f.get("RuleID", "") or f.get("Description", "")
        found[_key(rel, line, stype)] = {
            "repository": name, "file": rel,
            "secret_type": stype, "line_number": line,
        }
    return found


def _relpath(file_path: str, repo: Path) -> str:
    try:
        return Path(file_path).relative_to(repo).as_posix()
    except ValueError:
        return str(file_path).replace("\\", "/")


# ------------------------------------------------------------------ #
# Merge + dedup
# ------------------------------------------------------------------ #

def merge_repo(repo: Path) -> tuple[list[dict], dict]:
    name = folder_to_repo(repo.name)
    log.info("Scanning secrets in %s (gitleaks=%s, detect-secrets=yes) ...",
             name, "yes" if _GITLEAKS else "absent")
    gl = scan_gitleaks(repo, name)
    ds = scan_detect_secrets(repo, name)

    rows: list[dict] = []
    n_both = 0
    for k in set(gl) | set(ds):
        in_gl, in_ds = k in gl, k in ds
        base = gl.get(k) or ds.get(k)
        if in_gl and in_ds:
            detected_by = "both"
            n_both += 1
        elif in_gl:
            detected_by = "gitleaks"
        else:
            detected_by = "detect-secrets"
        rows.append({**base, "detected_by": detected_by})

    files = {r["file"] for r in rows}
    types = Counter(_norm_type(r["secret_type"]) for r in rows)
    summary = {
        "repository": name,
        "files_with_secrets": len(files),
        "total_secrets": len(rows),
        "by_gitleaks": len(gl),
        "by_detect_secrets": len(ds),
        "by_both": n_both,
        "types": "; ".join(f"{t}:{c}" for t, c in types.most_common()),
    }
    log.info("  %d unique secrets (%d both, %d gitleaks-only, %d ds-only)",
             len(rows), n_both, len(gl) - n_both, len(ds) - n_both)
    return rows, summary


def main() -> None:
    if not _GITLEAKS:
        log.warning("Gitleaks not found (set GITLEAKS_CLI / PATH / "
                    "E:\\developer-tools\\gitleaks). Running detect-secrets only.")

    all_findings: list[dict] = []
    summaries: list[dict] = []
    for repo in iter_repo_dirs():
        try:
            rows, summary = merge_repo(repo)
        except Exception as exc:  # noqa: BLE001
            log.warning("Secrets phase failed for %s: %s", repo.name, exc)
            continue
        all_findings.extend(rows)
        summaries.append(summary)

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
