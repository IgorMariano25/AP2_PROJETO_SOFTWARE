"""Phase 8 - Test metrics.

Per repository, counts test files, @Test methods, main/test LOC ratio and
detected testing frameworks. Writes data/tests.csv.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

from common import DATA_DIR, folder_to_repo, get_logger, iter_repo_dirs

log = get_logger("tests")

FRAMEWORK_PATTERNS = {
    "junit": re.compile(r"org\.junit|junit\.framework", re.I),
    "testng": re.compile(r"org\.testng", re.I),
    "mockito": re.compile(r"org\.mockito", re.I),
    "assertj": re.compile(r"org\.assertj", re.I),
    "spock": re.compile(r"spock\.lang", re.I),
}
TEST_ANNOTATION = re.compile(r"@Test\b")


def _count_loc(path: Path) -> int:
    try:
        return sum(1 for line in path.read_text(encoding="utf-8", errors="ignore")
                   .splitlines() if line.strip())
    except Exception:  # noqa: BLE001
        return 0


def analyze_repo(repo: Path) -> dict:
    name = folder_to_repo(repo.name)
    test_files = 0
    test_methods = 0
    main_loc = 0
    test_loc = 0
    frameworks: set[str] = set()

    for path in repo.rglob("*.java"):
        p = path.as_posix()
        if "/.git/" in p:
            continue
        is_test = "/src/test/" in p or p.endswith("Test.java") or p.endswith("Tests.java")
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:  # noqa: BLE001
            continue
        loc = sum(1 for line in text.splitlines() if line.strip())

        if is_test:
            test_files += 1
            test_loc += loc
            test_methods += len(TEST_ANNOTATION.findall(text))
            for fw, pat in FRAMEWORK_PATTERNS.items():
                if pat.search(text):
                    frameworks.add(fw)
        else:
            main_loc += loc

    ratio = round(test_loc / main_loc, 4) if main_loc else 0.0
    return {
        "repository": name,
        "test_files": test_files,
        "test_methods": test_methods,
        "main_loc": main_loc,
        "test_loc": test_loc,
        "test_to_main_ratio": ratio,
        "frameworks": ";".join(sorted(frameworks)),
    }


def main() -> None:
    rows = []
    for repo in iter_repo_dirs():
        log.info("Tests for %s ...", repo.name)
        try:
            rows.append(analyze_repo(repo))
        except Exception as exc:  # noqa: BLE001
            log.warning("Test metrics failed for %s: %s", repo.name, exc)

    out = DATA_DIR / "tests.csv"
    fields = ["repository", "test_files", "test_methods", "main_loc",
              "test_loc", "test_to_main_ratio", "frameworks"]
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    log.info("Wrote %d rows to %s", len(rows), out.name)


if __name__ == "__main__":
    main()
