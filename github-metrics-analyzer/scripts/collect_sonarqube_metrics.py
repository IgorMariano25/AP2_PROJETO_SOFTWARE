"""Phase S2 - Structural / maintainability metrics via SonarQube (source-only).

CANONICAL source of structural features for the ML dataset (complexity,
cognitive complexity, duplication, code smells, comment density, size).
When data/sonarqube.csv exists, build_security_dataset.py uses it INSTEAD of
the lizard-derived complexity columns — one source per dimension (no
double-counting / multicollinearity). If SonarQube is unavailable, lizard
remains the offline fallback.

IMPORTANT (study rule §9.1): SonarQube is NOT the security oracle. Without
bytecode its Java taint/security rules do not fire, so `vulnerabilities` is
near-empty. We use it ONLY for structural metrics; the security target comes
from Semgrep/CodeQL. Security-derived measures are therefore excluded from the
ML features.

Pipeline per repo (static, no project build):
  1. sonar-scanner  with sonar.sources=<repo>, source-only flags
  2. poll  GET /api/ce/task  until the background analysis completes
  3. read  GET /api/measures/component_tree?qualifiers=FIL  (per-file metrics)
     — never scraped from the dashboard (study §6 requires the Web API)

Configuration (env / .env):
  SONAR_HOST_URL   default http://localhost:9000
  SONAR_TOKEN      analysis + API token (required)
  SONARSCANNER_CLI optional explicit path to the sonar-scanner executable

The SonarScanner CLI is a heavy external binary (not pip), resolved via
SONARSCANNER_CLI, PATH, or E:\\developer-tools\\sonar-scanner.

Output:
  data/sonarqube.csv — one row per .java file
"""
from __future__ import annotations

import csv
import os
import time
from pathlib import Path

import requests

from common import (DATA_DIR, find_external_tool, folder_to_repo, get_logger,
                    iter_repo_dirs, repo_to_folder, run_command)

log = get_logger("sonarqube")

SONAR_HOST = os.getenv("SONAR_HOST_URL", "http://localhost:9000").rstrip("/")
SONAR_TOKEN = os.getenv("SONAR_TOKEN", "")

# Structural metrics only (no security-derived measures → no ML leakage).
METRIC_KEYS = [
    "ncloc", "lines", "functions", "classes", "statements",
    "complexity", "cognitive_complexity",
    "duplicated_lines", "duplicated_lines_density", "duplicated_blocks",
    "comment_lines", "comment_lines_density",
    "code_smells", "sqale_index", "sqale_debt_ratio",
    "violations", "blocker_violations", "critical_violations",
    "major_violations", "minor_violations",
]

FIELDS = ["repository", "file"] + METRIC_KEYS

_SCANNER = find_external_tool(
    "SONARSCANNER_CLI", ("sonar-scanner", "sonar-scanner.bat", "sonar-scanner.exe"),
    subdirs=("sonar-scanner",),
)


def _api_get(path: str, params: dict) -> dict | None:
    """GET the SonarQube Web API with token auth (token as username)."""
    try:
        resp = requests.get(f"{SONAR_HOST}{path}", params=params,
                            auth=(SONAR_TOKEN, ""), timeout=60)
        if resp.status_code == 200:
            return resp.json()
        log.warning("API %s -> %s: %s", path, resp.status_code, resp.text[:200])
    except requests.RequestException as exc:
        log.warning("API request failed (%s): %s", path, exc)
    return None


def _run_scanner(repo: Path, project_key: str) -> bool:
    """Run sonar-scanner over a repo in source-only mode. Returns success."""
    # sonar.java.binaries is mandatory for the Java analyzer; in a no-build
    # study we point it at the sources themselves so AST-based metrics still
    # compute. Security/bug rules that need bytecode simply won't fire (§9.1).
    cmd = (
        f'"{_SCANNER}" '
        f'-Dsonar.host.url={SONAR_HOST} '
        f'-Dsonar.token={SONAR_TOKEN} '
        f'-Dsonar.projectKey={project_key} '
        f'-Dsonar.projectName={project_key} '
        f'-Dsonar.sources="{repo}" '
        f'-Dsonar.java.binaries="{repo}" '
        f'-Dsonar.exclusions="**/*.jar,**/.git/**" '
        f'-Dsonar.scm.disabled=true '
        f'-Dsonar.sourceEncoding=UTF-8'
    )
    log.info("SonarScanner analysing %s ...", project_key)
    out = run_command(cmd, cwd=repo, timeout=3600)
    if "EXECUTION SUCCESS" in out or "ANALYSIS SUCCESSFUL" in out:
        return True
    # run_command swallows stderr; treat empty/!success as failure but try the
    # API anyway in case the analysis was submitted.
    log.warning("Scanner did not report success for %s (tail: %s)",
                project_key, out[-300:] if out else "no output")
    return bool(out)


def _wait_for_analysis(project_key: str, max_wait: int = 300) -> None:
    """Poll the compute-engine queue until the project's analysis is done."""
    waited = 0
    while waited < max_wait:
        data = _api_get("/api/ce/component", {"component": project_key})
        if data is not None:
            queue = data.get("queue", [])
            current = data.get("current")
            if not queue and (current is None or current.get("status") in
                              ("SUCCESS", "FAILED", "CANCELED")):
                return
        time.sleep(5)
        waited += 5
    log.warning("Timed out waiting for analysis of %s", project_key)


def _fetch_file_measures(repo_name: str, project_key: str) -> list[dict]:
    """Page through component_tree (qualifier=FIL) collecting per-file metrics."""
    rows: list[dict] = []
    page = 1
    while True:
        data = _api_get("/api/measures/component_tree", {
            "component": project_key,
            "qualifiers": "FIL",
            "metricKeys": ",".join(METRIC_KEYS),
            "ps": 500,
            "p": page,
        })
        if data is None:
            break
        components = data.get("components", [])
        for comp in components:
            measures = {m["metric"]: m.get("value", "")
                        for m in comp.get("measures", [])}
            # component path is relative to the project (== repo) root.
            file_path = comp.get("path") or comp.get("key", "").split(":")[-1]
            row = {"repository": repo_name,
                   "file": file_path.replace("\\", "/").lstrip("./")}
            for k in METRIC_KEYS:
                row[k] = measures.get(k, "")
            rows.append(row)
        total = data.get("paging", {}).get("total", 0)
        if page * 500 >= total or not components:
            break
        page += 1
    return rows


def collect_repo(repo: Path) -> list[dict]:
    name = folder_to_repo(repo.name)
    project_key = repo_to_folder(name)
    if not _run_scanner(repo, project_key):
        return []
    _wait_for_analysis(project_key)
    rows = _fetch_file_measures(name, project_key)
    log.info("  %d files with measures for %s", len(rows), name)
    return rows


def main() -> None:
    out = DATA_DIR / "sonarqube.csv"

    if not _SCANNER or not SONAR_TOKEN:
        missing = []
        if not _SCANNER:
            missing.append("sonar-scanner (set SONARSCANNER_CLI / PATH / "
                           "E:\\developer-tools\\sonar-scanner)")
        if not SONAR_TOKEN:
            missing.append("SONAR_TOKEN env var")
        log.warning("SonarQube prerequisites missing: %s. Writing empty file; "
                    "the dataset will fall back to lizard for complexity.",
                    "; ".join(missing))
        with open(out, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=FIELDS).writeheader()
        return

    log.info("Using SonarScanner: %s  |  host: %s", _SCANNER, SONAR_HOST)
    all_rows: list[dict] = []
    for repo in iter_repo_dirs():
        try:
            all_rows.extend(collect_repo(repo))
        except Exception as exc:  # noqa: BLE001
            log.warning("SonarQube phase failed for %s: %s", repo.name, exc)

    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_rows)
    log.info("Wrote %d file rows to %s", len(all_rows), out.name)


if __name__ == "__main__":
    main()
