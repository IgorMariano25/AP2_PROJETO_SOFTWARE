"""Phase 5 - Lines of Code metrics.

Uses `cloc` (preferred, JSON output) and falls back to `scc`/`tokei` or a
simple Python line counter. Writes data/loc.csv (one row per repo, Java focus
plus overall totals).
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from common import (DATA_DIR, command_exists, folder_to_repo, get_logger,
                    iter_repo_dirs, run_command)

log = get_logger("loc")


def via_cloc(repo: Path) -> dict | None:
    out = run_command(
        'cloc --json --quiet --timeout 0 .', cwd=repo, timeout=1800)
    if not out:
        return None
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return None
    java = data.get("Java", {})
    total = data.get("SUM", {})
    return {
        "files": total.get("nFiles", 0),
        "blank": total.get("blank", 0),
        "comment": total.get("comment", 0),
        "code": total.get("code", 0),
        "java_files": java.get("nFiles", 0),
        "java_code": java.get("code", 0),
        "java_comment": java.get("comment", 0),
        "java_blank": java.get("blank", 0),
    }


def via_python(repo: Path) -> dict:
    """Last-resort Java-only line counter."""
    files = code = comment = blank = 0
    for path in repo.rglob("*.java"):
        if "/.git/" in path.as_posix():
            continue
        files += 1
        try:
            for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                s = line.strip()
                if not s:
                    blank += 1
                elif s.startswith(("//", "*", "/*")):
                    comment += 1
                else:
                    code += 1
        except Exception:  # noqa: BLE001
            continue
    return {"files": files, "blank": blank, "comment": comment, "code": code,
            "java_files": files, "java_code": code, "java_comment": comment,
            "java_blank": blank}


def main() -> None:
    has_cloc = command_exists("cloc")
    if not has_cloc:
        log.warning("cloc not found; using built-in Java line counter.")

    rows = []
    for repo in iter_repo_dirs():
        log.info("LOC for %s ...", repo.name)
        metrics = (via_cloc(repo) if has_cloc else None) or via_python(repo)
        metrics["repository"] = folder_to_repo(repo.name)
        rows.append(metrics)

    out = DATA_DIR / "loc.csv"
    fields = ["repository", "files", "blank", "comment", "code", "java_files",
              "java_code", "java_comment", "java_blank"]
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, 0) for k in fields})
    log.info("Wrote %d rows to %s", len(rows), out.name)


if __name__ == "__main__":
    main()
