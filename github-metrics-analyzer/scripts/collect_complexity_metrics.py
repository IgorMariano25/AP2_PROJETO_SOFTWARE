"""Phase 6 - Cyclomatic complexity per method using `lizard`.

Writes data/complexity.csv with one row per Java method: NLOC, CCN, token
count and parameter count. Uses the lizard Python API directly (no subprocess).
"""
from __future__ import annotations

import csv
from pathlib import Path

from common import DATA_DIR, folder_to_repo, get_logger, iter_repo_dirs

log = get_logger("complexity")

try:
    import lizard
except ImportError:  # pragma: no cover
    lizard = None


def analyze_repo(repo: Path) -> list[dict]:
    name = folder_to_repo(repo.name)
    rows = []
    for path in repo.rglob("*.java"):
        if "/.git/" in path.as_posix():
            continue
        try:
            info = lizard.analyze_file(str(path))
        except Exception:  # noqa: BLE001
            continue
        rel = path.relative_to(repo).as_posix()
        for fn in info.function_list:
            rows.append({
                "repository": name,
                "file": rel,
                "method": fn.name,
                "nloc": fn.nloc,
                "ccn": fn.cyclomatic_complexity,
                "tokens": fn.token_count,
                "parameters": len(fn.parameters),
                "length": fn.length,
            })
    return rows


def main() -> None:
    if lizard is None:
        log.error("lizard is not installed. Run: pip install lizard")
        # still emit an empty file so downstream phases don't crash
        _write([], )
        return

    all_rows = []
    for repo in iter_repo_dirs():
        log.info("Complexity for %s ...", repo.name)
        try:
            all_rows.extend(analyze_repo(repo))
        except Exception as exc:  # noqa: BLE001
            log.warning("Complexity failed for %s: %s", repo.name, exc)
    _write(all_rows)


def _write(rows: list[dict]) -> None:
    out = DATA_DIR / "complexity.csv"
    fields = ["repository", "file", "method", "nloc", "ccn", "tokens",
              "parameters", "length"]
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    log.info("Wrote %d method rows to %s", len(rows), out.name)


if __name__ == "__main__":
    main()
