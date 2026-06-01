"""Phase 4 - Collect Pull Request metrics from the GitHub REST API.

For each repository pulls PRs (state=all, paginated) and, for a bounded sample,
the number of commits per PR. Writes data/pull_requests.csv.
"""
from __future__ import annotations

import csv
from datetime import datetime

from common import (DATA_DIR, get_logger, github_get, github_paginate,
                    read_repo_list)

log = get_logger("pr")

# Limit commit-count lookups to avoid burning the API budget on huge repos.
MAX_PRS_PER_REPO = 300
COMMITS_LOOKUP_LIMIT = 150


def _hours_between(a: str, b: str) -> float | str:
    if not a or not b:
        return ""
    try:
        d1 = datetime.fromisoformat(a.replace("Z", "+00:00"))
        d2 = datetime.fromisoformat(b.replace("Z", "+00:00"))
        return round((d2 - d1).total_seconds() / 3600, 2)
    except ValueError:
        return ""


def collect_repo_prs(full_name: str) -> list[dict]:
    rows = []
    url = f"https://api.github.com/repos/{full_name}/pulls"
    params = {"state": "all", "sort": "created", "direction": "desc"}

    count = 0
    for pr in github_paginate(url, params=params):
        if count >= MAX_PRS_PER_REPO:
            break
        count += 1

        merged_at = pr.get("merged_at") or ""
        closed_at = pr.get("closed_at") or ""
        created_at = pr.get("created_at") or ""
        state = "merged" if merged_at else pr.get("state", "")

        commits = ""
        if count <= COMMITS_LOOKUP_LIMIT:
            try:
                resp = github_get(
                    f"https://api.github.com/repos/{full_name}/pulls/"
                    f"{pr['number']}/commits",
                    params={"per_page": 1})
                # Total count is exposed via the Link header's last page.
                link = resp.headers.get("Link", "")
                if 'rel="last"' in link:
                    import re
                    m = re.search(r'[?&]page=(\d+)>; rel="last"', link)
                    commits = int(m.group(1)) if m else len(resp.json())
                else:
                    commits = len(resp.json())
            except Exception:  # noqa: BLE001
                commits = ""

        rows.append({
            "repository": full_name,
            "number": pr.get("number"),
            "state": state,
            "created_at": created_at,
            "closed_at": closed_at,
            "merged_at": merged_at,
            "hours_to_close": _hours_between(created_at, closed_at or merged_at),
            "commits": commits,
            "author": (pr.get("user") or {}).get("login", ""),
        })
    return rows


def main() -> None:
    repos = read_repo_list()
    all_rows = []
    for name in repos:
        log.info("Pull requests for %s ...", name)
        try:
            all_rows.extend(collect_repo_prs(name))
        except Exception as exc:  # noqa: BLE001
            log.warning("PR collection failed for %s: %s", name, exc)

    out = DATA_DIR / "pull_requests.csv"
    fields = ["repository", "number", "state", "created_at", "closed_at",
              "merged_at", "hours_to_close", "commits", "author"]
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(all_rows)
    log.info("Wrote %d PR rows to %s", len(all_rows), out.name)


if __name__ == "__main__":
    main()
