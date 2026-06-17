"""Phase S4 - SCA (Software Composition Analysis) via OSV API.

Parses pom.xml (Maven) and build.gradle / build.gradle.kts (Gradle) manifests
to extract declared dependencies, then queries the OSV API
(https://api.osv.dev/v1/query) for known vulnerabilities.

Limitation (declare in paper): only DIRECT dependencies from manifests are
resolved.  Transitive dependencies require a full Maven/Gradle dependency
resolution (which needs build tooling).  This is an inherent constraint of
static analysis without build.

Output:
  data/osv_findings.csv  — one row per repo-level CVE finding
    columns: repository, package_name, version, vuln_id, severity_score,
             severity_label, title

  data/osv_summary.csv   — one row per repository
    columns: repository, deps_found, vulns_direct, vulns_critical,
             vulns_high, vulns_medium, vulns_low, avg_cvss
"""
from __future__ import annotations

import csv
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

from common import DATA_DIR, folder_to_repo, get_logger, iter_repo_dirs

log = get_logger("osv")

OSV_API = "https://api.osv.dev/v1/query"
OSV_BATCH = "https://api.osv.dev/v1/querybatch"

FINDING_FIELDS = [
    "repository", "package_name", "version",
    "vuln_id", "severity_score", "severity_label", "title",
]
SUMMARY_FIELDS = [
    "repository", "deps_declared", "deps_queryable",
    "vulns_direct", "vulns_critical", "vulns_high",
    "vulns_medium", "vulns_low", "avg_cvss",
]

NS = {"m": "http://maven.apache.org/POM/4.0.0"}


# ------------------------------------------------------------------ #
# Manifest parsers
# ------------------------------------------------------------------ #

def _parse_pom(pom: Path) -> list[tuple[str, str, str]]:
    """Return [(groupId, artifactId, version)] from a pom.xml.

    version may be "" when the POM inherits it from a parent's
    <dependencyManagement> (very common in multi-module Maven projects like
    DataWave). Such version-less deps are still counted as *declared* but are
    NOT queryable against OSV (OSV needs an exact version). This split is what
    makes the SCA-without-build limitation explicit and honest.
    """
    deps = []
    try:
        tree = ET.parse(pom)
        root = tree.getroot()
        # namespace-aware; fall back to no-namespace
        tag = lambda t: f"{{{NS['m']}}}{t}"  # noqa: E731
        dep_tags = root.findall(f".//{tag('dependency')}")
        if not dep_tags:
            dep_tags = root.findall(".//dependency")
            tag = lambda t: t  # noqa: E731

        for dep in dep_tags:
            # NOTE: must use `is not None` — an ElementTree Element with no
            # child elements is falsy, so `find(...) or default` would wrongly
            # discard valid leaf elements that carry text.
            g = _text(dep.find(tag("groupId")))
            a = _text(dep.find(tag("artifactId")))
            v = _text(dep.find(tag("version")))
            # Drop property placeholders like ${spring.version} (unresolvable
            # without build) — treat as version-less.
            if v.startswith("$"):
                v = ""
            if g and a:
                deps.append((g, a, v))
    except Exception as exc:  # noqa: BLE001
        log.debug("pom parse error %s: %s", pom, exc)
    return deps


def _text(elem) -> str:
    """Safe text extraction from an ElementTree element (handles None)."""
    if elem is None or elem.text is None:
        return ""
    return elem.text.strip()


_GRADLE_DEP_RE = re.compile(
    r"""(?:implementation|api|compile|runtimeOnly|testImplementation)\s*
        ['"]([\w.\-]+):([\w.\-]+):([\w.\-]+)['"]""",
    re.VERBOSE,
)


def _parse_gradle(gradle: Path) -> list[tuple[str, str, str]]:
    """Return [(groupId, artifactId, version)] from a build.gradle file."""
    deps = []
    try:
        text = gradle.read_text(encoding="utf-8", errors="ignore")
        for m in _GRADLE_DEP_RE.finditer(text):
            g, a, v = m.group(1), m.group(2), m.group(3)
            if not v.startswith("$"):
                deps.append((g, a, v))
    except Exception as exc:  # noqa: BLE001
        log.debug("gradle parse error %s: %s", gradle, exc)
    return deps


def collect_deps(repo: Path) -> list[tuple[str, str, str]]:
    """Collect all declared Maven/Gradle deps from a repo (deduplicated)."""
    seen: set[tuple[str, str, str]] = set()
    deps: list[tuple[str, str, str]] = []

    for pom in repo.rglob("pom.xml"):
        if ".git" in pom.parts:
            continue
        for d in _parse_pom(pom):
            if d not in seen:
                seen.add(d)
                deps.append(d)

    for gradle in list(repo.rglob("build.gradle")) + list(
            repo.rglob("build.gradle.kts")):
        if ".git" in gradle.parts:
            continue
        for d in _parse_gradle(gradle):
            if d not in seen:
                seen.add(d)
                deps.append(d)

    return deps


# ------------------------------------------------------------------ #
# OSV query
# ------------------------------------------------------------------ #

def _cvss_label(score: float) -> str:
    if score >= 9.0:
        return "CRITICAL"
    if score >= 7.0:
        return "HIGH"
    if score >= 4.0:
        return "MEDIUM"
    return "LOW"


def query_osv_batch(deps: list[tuple[str, str, str]]) -> list[dict]:
    """Query OSV batch endpoint; return list of finding dicts.

    Only deps with an explicit version are queryable (OSV needs an exact
    version). Version-less deps are silently skipped here — the caller counts
    them separately for the descriptive 'declared vs queryable' split.
    """
    deps = [(g, a, v) for (g, a, v) in deps if v]
    if not deps:
        return []

    queries = []
    for g, a, v in deps:
        queries.append({
            "version": v,
            "package": {"name": f"{g}:{a}", "ecosystem": "Maven"},
        })

    findings: list[dict] = []
    chunk_size = 50
    for i in range(0, len(queries), chunk_size):
        chunk = queries[i: i + chunk_size]
        chunk_deps = deps[i: i + chunk_size]
        try:
            resp = requests.post(
                OSV_BATCH,
                json={"queries": chunk},
                timeout=60,
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
        except Exception as exc:  # noqa: BLE001
            log.warning("OSV batch query error: %s", exc)
            time.sleep(2)
            continue

        for j, result in enumerate(results):
            g, a, v = chunk_deps[j]
            pkg_name = f"{g}:{a}"
            for vuln in result.get("vulns", []):
                vuln_id = vuln.get("id", "")
                title = (vuln.get("summary") or "")[:200]
                # Extract CVSS score from severity list
                score = 0.0
                for sev in vuln.get("severity", []):
                    raw = sev.get("score", "")
                    # CVSS v3 score is in format "CVSS:3.1/AV:N/..."
                    # or just a numeric string
                    try:
                        score = max(score, float(raw.split("/")[0].replace("CVSS:3.1", "").replace("CVSS:3.0", "").strip() or 0))
                    except ValueError:
                        pass
                    # Also try database_specific.severity
                    if score == 0.0:
                        db_sev = vuln.get("database_specific", {}).get("severity", "")
                        sev_map = {"CRITICAL": 9.5, "HIGH": 8.0, "MEDIUM": 5.0, "LOW": 2.0}
                        score = sev_map.get(db_sev.upper(), 0.0)

                findings.append({
                    "package_name": pkg_name,
                    "version": v,
                    "vuln_id": vuln_id,
                    "severity_score": round(score, 1),
                    "severity_label": _cvss_label(score),
                    "title": title,
                })

        time.sleep(0.2)  # be polite

    return findings


# ------------------------------------------------------------------ #
# Main
# ------------------------------------------------------------------ #

def main() -> None:
    all_findings: list[dict] = []
    summaries: list[dict] = []

    for repo in iter_repo_dirs():
        name = folder_to_repo(repo.name)
        log.info("OSV SCA for %s ...", name)

        deps = collect_deps(repo)
        queryable = [d for d in deps if d[2]]
        log.info("  Declared deps: %d  (queryable with version: %d)",
                 len(deps), len(queryable))

        findings = query_osv_batch(deps)

        for f in findings:
            all_findings.append({"repository": name, **f})

        scores = [f["severity_score"] for f in findings if f["severity_score"] > 0]
        summaries.append({
            "repository": name,
            "deps_declared": len(deps),
            "deps_queryable": len(queryable),
            "vulns_direct": len(findings),
            "vulns_critical": sum(1 for f in findings if f["severity_label"] == "CRITICAL"),
            "vulns_high": sum(1 for f in findings if f["severity_label"] == "HIGH"),
            "vulns_medium": sum(1 for f in findings if f["severity_label"] == "MEDIUM"),
            "vulns_low": sum(1 for f in findings if f["severity_label"] == "LOW"),
            "avg_cvss": round(sum(scores) / len(scores), 2) if scores else 0.0,
        })
        log.info("  %d CVEs found for %s", len(findings), name)

    _write_csv(DATA_DIR / "osv_findings.csv", all_findings, FINDING_FIELDS)
    _write_csv(DATA_DIR / "osv_summary.csv", summaries, SUMMARY_FIELDS)


def _write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    log.info("Wrote %d rows to %s", len(rows), path.name)


if __name__ == "__main__":
    main()
