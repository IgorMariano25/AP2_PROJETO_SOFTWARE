"""Phase 1 - Search large, active Java repositories.

Uses the GitHub Search REST API (or the `gh` CLI if available) to find ~10
large Java repositories, validates them (not archived, Java primary language,
recent activity) and writes:

  * repos.txt              -> one ``owner/repo`` per line
  * data/repositories.csv  -> full metadata
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone

from common import (DATA_DIR, REPOS_TXT, command_exists, get_logger,
                    github_get, run_command)

log = get_logger("search")

# Curated fallback list (used if the API/CLI is unavailable).
FALLBACK_REPOS = [
    "spring-projects/spring-boot",
    "spring-projects/spring-framework",
    "apache/kafka",
    "apache/cassandra",
    "apache/dubbo",
    "elastic/elasticsearch",
    "ReactiveX/RxJava",
    "google/guava",
    "square/retrofit",
    "alibaba/nacos",
]

SEARCH_QUERY = "language:Java stars:>5000 forks:>1000 archived:false"
TARGET_COUNT = 10
MAX_INACTIVE_DAYS = 365


def _recent_enough(pushed_at: str) -> bool:
    if not pushed_at:
        return False
    try:
        dt = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    age = (datetime.now(timezone.utc) - dt).days
    return age <= MAX_INACTIVE_DAYS


def _normalize(repo: dict) -> dict:
    """Normalize a record coming from either the REST API or the gh CLI."""
    return {
        "full_name": repo.get("full_name") or repo.get("fullName"),
        "url": repo.get("html_url") or repo.get("url"),
        "stars": repo.get("stargazers_count", repo.get("stargazersCount", 0)),
        "forks": repo.get("forks_count", repo.get("forksCount", 0)),
        "open_issues": repo.get("open_issues_count", 0),
        "language": repo.get("language", ""),
        "license": (repo.get("license") or {}).get("spdx_id", "")
        if isinstance(repo.get("license"), dict) else (repo.get("license") or ""),
        "pushed_at": repo.get("pushed_at") or repo.get("pushedAt", ""),
        "archived": repo.get("archived", repo.get("isArchived", False)),
        "description": (repo.get("description") or "").replace("\n", " "),
    }


def search_via_api() -> list[dict]:
    log.info("Searching repositories via GitHub REST API ...")
    resp = github_get(
        "https://api.github.com/search/repositories",
        params={"q": SEARCH_QUERY, "sort": "stars", "order": "desc",
                "per_page": 30},
    )
    return [_normalize(r) for r in resp.json().get("items", [])]


def search_via_cli() -> list[dict]:
    log.info("Searching repositories via GitHub CLI (gh) ...")
    out = run_command(
        'gh search repos --language Java --stars ">5000" --forks ">1000" '
        '--archived=false --sort stars --order desc --limit 30 '
        "--json fullName,url,stargazersCount,forksCount,pushedAt,"
        "description,isArchived,language"
    )
    if not out:
        return []
    try:
        return [_normalize(r) for r in json.loads(out)]
    except json.JSONDecodeError:
        return []


def validate(repos: list[dict]) -> list[dict]:
    valid, seen = [], set()
    for r in repos:
        name = r["full_name"]
        if not name or name in seen:
            continue
        if r.get("archived"):
            log.info("Skip %s (archived)", name)
            continue
        if (r.get("language") or "").lower() != "java":
            log.info("Skip %s (primary language=%s)", name, r.get("language"))
            continue
        if not _recent_enough(r.get("pushed_at", "")):
            log.info("Skip %s (inactive)", name)
            continue
        seen.add(name)
        valid.append(r)
    return valid


def fetch_fallback_metadata() -> list[dict]:
    log.warning("Falling back to curated repository list.")
    repos = []
    for name in FALLBACK_REPOS:
        try:
            resp = github_get(f"https://api.github.com/repos/{name}")
            repos.append(_normalize(resp.json()))
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not fetch %s: %s", name, exc)
            repos.append({"full_name": name, "url": f"https://github.com/{name}",
                          "stars": 0, "forks": 0, "open_issues": 0,
                          "language": "Java", "license": "", "pushed_at": "",
                          "archived": False, "description": ""})
    return repos


def main() -> None:
    repos: list[dict] = []
    try:
        repos = search_via_api()
    except Exception as exc:  # noqa: BLE001
        log.warning("REST search failed: %s", exc)

    if not repos and command_exists("gh"):
        repos = search_via_cli()

    valid = validate(repos)

    if len(valid) < TARGET_COUNT:
        valid = validate(fetch_fallback_metadata()) or fetch_fallback_metadata()

    selected = valid[:TARGET_COUNT]

    REPOS_TXT.write_text(
        "\n".join(r["full_name"] for r in selected) + "\n", encoding="utf-8")
    log.info("Wrote %d repositories to %s", len(selected), REPOS_TXT)

    out_csv = DATA_DIR / "repositories.csv"
    fields = ["full_name", "url", "stars", "forks", "open_issues", "language",
              "license", "pushed_at", "archived", "description"]
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in selected:
            writer.writerow({k: r.get(k, "") for k in fields})
    log.info("Wrote metadata to %s", out_csv)


if __name__ == "__main__":
    main()
