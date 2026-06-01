"""Phase 3 - Collect Git metrics from local clones.

Produces three CSVs from the Git history (no API used here):

  * data/commits.csv     -> per-repo commit summary (total, first/last, active days)
  * data/developers.csv  -> per-developer commit counts
  * data/files.csv       -> per-file commit counts + lines added/removed
"""
from __future__ import annotations

import csv
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from common import DATA_DIR, folder_to_repo, get_logger, iter_repo_dirs, run_command

log = get_logger("git")

SHORTLOG_RE = re.compile(r"^\s*(\d+)\s+(.+?)\s+<(.*?)>\s*$")


def collect_commit_summary(repo: Path) -> dict:
    name = folder_to_repo(repo.name)
    total = run_command("git rev-list --count HEAD", cwd=repo) or "0"
    first = run_command(
        'git log --reverse --format=%cI --max-parents=0', cwd=repo)
    first = first.splitlines()[0] if first else ""
    last = run_command("git log -1 --format=%cI", cwd=repo)

    active_days = 0
    if first and last:
        try:
            d1 = datetime.fromisoformat(first.replace("Z", "+00:00"))
            d2 = datetime.fromisoformat(last.replace("Z", "+00:00"))
            active_days = (d2 - d1).days
        except ValueError:
            pass

    # distinct days with at least one commit
    days = run_command("git log --format=%cd --date=short", cwd=repo)
    distinct_days = len(set(days.splitlines())) if days else 0

    return {
        "repository": name,
        "total_commits": int(total) if total.isdigit() else 0,
        "first_commit": first,
        "last_commit": last,
        "span_days": active_days,
        "distinct_active_days": distinct_days,
    }


def collect_developers(repo: Path) -> list[dict]:
    name = folder_to_repo(repo.name)
    out = run_command("git shortlog -sne --all --no-merges", cwd=repo)
    rows = []
    for line in out.splitlines():
        m = SHORTLOG_RE.match(line)
        if m:
            rows.append({
                "repository": name,
                "developer": m.group(2).strip(),
                "email": m.group(3).strip(),
                "commits": int(m.group(1)),
            })
    return rows


def collect_files(repo: Path, limit: int = 2000) -> list[dict]:
    """Aggregate commits and line churn per file using git log --numstat."""
    name = folder_to_repo(repo.name)
    out = run_command(
        'git log --numstat --no-merges --format="C%H"', cwd=repo, timeout=1800)

    commits = defaultdict(int)
    added = defaultdict(int)
    removed = defaultdict(int)

    for line in out.splitlines():
        if line.startswith("C"):  # commit marker line
            continue
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        a, r, path = parts
        commits[path] += 1
        if a.isdigit():
            added[path] += int(a)
        if r.isdigit():
            removed[path] += int(r)

    rows = [{
        "repository": name,
        "file": path,
        "commits": commits[path],
        "lines_added": added[path],
        "lines_removed": removed[path],
    } for path in commits]

    rows.sort(key=lambda x: x["commits"], reverse=True)
    return rows[:limit]


def main() -> None:
    summaries, developers, files = [], [], []
    for repo in iter_repo_dirs():
        log.info("Git metrics for %s ...", repo.name)
        try:
            summaries.append(collect_commit_summary(repo))
            developers.extend(collect_developers(repo))
            files.extend(collect_files(repo))
        except Exception as exc:  # noqa: BLE001
            log.warning("Git metrics failed for %s: %s", repo.name, exc)

    _write(DATA_DIR / "commits.csv", summaries,
           ["repository", "total_commits", "first_commit", "last_commit",
            "span_days", "distinct_active_days"])
    _write(DATA_DIR / "developers.csv", developers,
           ["repository", "developer", "email", "commits"])
    _write(DATA_DIR / "files.csv", files,
           ["repository", "file", "commits", "lines_added", "lines_removed"])


def _write(path: Path, rows: list[dict], fields: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    log.info("Wrote %d rows to %s", len(rows), path.name)


if __name__ == "__main__":
    main()
