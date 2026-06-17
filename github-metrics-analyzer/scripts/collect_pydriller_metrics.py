"""Phase S2 - Process metrics per Java file via PyDriller.

Metrics collected (ISO/IEC 25010 / 25023 mapping: Manutenibilidade):
  commits           — number of commits that touched the file
  distinct_authors  — number of distinct developers who modified the file
  lines_added       — total lines added across all commits
  lines_removed     — total lines removed across all commits
  churn             — lines_added + lines_removed
  file_age_days     — days between first and last commit of the file
  days_since_change — days from last commit to collection date

Output:
  data/pydriller_metrics.csv — one row per Java file per repository
"""
from __future__ import annotations

import csv
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from common import DATA_DIR, get_logger, iter_repo_dirs, folder_to_repo

log = get_logger("pydriller")

try:
    from pydriller import Repository
    from pydriller.domain.commit import ModificationType
except ImportError:  # pragma: no cover
    Repository = None  # type: ignore

FIELDS = [
    "repository", "file",
    "commits", "distinct_authors",
    "lines_added", "lines_removed", "churn",
    "file_age_days", "days_since_change",
]

_NOW = datetime.now(tz=timezone.utc)


def analyze_repo(repo_path: Path) -> list[dict]:
    name = folder_to_repo(repo_path.name)
    log.info("PyDriller processing %s ...", name)

    commits: defaultdict[str, int] = defaultdict(int)
    authors: defaultdict[str, set] = defaultdict(set)
    added: defaultdict[str, int] = defaultdict(int)
    removed: defaultdict[str, int] = defaultdict(int)
    first_seen: dict[str, datetime] = {}
    last_seen: dict[str, datetime] = {}

    try:
        for commit in Repository(str(repo_path), only_modifications_with_file_types=[".java"]).traverse_commits():
            when = commit.committer_date
            if when and when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)

            dev_id = commit.author.email or commit.author.name

            for mod in commit.modified_files:
                if not (mod.filename or "").endswith(".java"):
                    continue

                # Use new_path when available; fall back to old_path (deletions)
                fpath = mod.new_path or mod.old_path
                if not fpath:
                    continue

                commits[fpath] += 1
                authors[fpath].add(dev_id)
                added[fpath] += mod.added_lines or 0
                removed[fpath] += mod.deleted_lines or 0

                if when:
                    if fpath not in first_seen or when < first_seen[fpath]:
                        first_seen[fpath] = when
                    if fpath not in last_seen or when > last_seen[fpath]:
                        last_seen[fpath] = when

    except Exception as exc:  # noqa: BLE001
        log.warning("PyDriller error in %s: %s", name, exc)

    rows = []
    for fpath in commits:
        fa = first_seen.get(fpath)
        la = last_seen.get(fpath)

        age = int((la - fa).days) if fa and la and la > fa else 0
        since = int((_NOW - la).days) if la else -1

        rows.append({
            "repository": name,
            "file": fpath,
            "commits": commits[fpath],
            "distinct_authors": len(authors[fpath]),
            "lines_added": added[fpath],
            "lines_removed": removed[fpath],
            "churn": added[fpath] + removed[fpath],
            "file_age_days": age,
            "days_since_change": since,
        })

    log.info("  %d Java file records for %s", len(rows), name)
    return rows


def main() -> None:
    if Repository is None:
        log.error("pydriller is not installed. Run: pip install pydriller")
        _write([])
        return

    all_rows: list[dict] = []
    for repo in iter_repo_dirs():
        try:
            all_rows.extend(analyze_repo(repo))
        except Exception as exc:  # noqa: BLE001
            log.warning("PyDriller phase failed for %s: %s", repo.name, exc)

    _write(all_rows)


def _write(rows: list[dict]) -> None:
    out = DATA_DIR / "pydriller_metrics.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    log.info("Wrote %d rows to %s", len(rows), out.name)


if __name__ == "__main__":
    main()
