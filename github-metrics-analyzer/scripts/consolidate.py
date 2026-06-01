"""Phase 9 - Consolidate all CSVs into SQLite (optional) for easy querying.

Loads every data/*.csv with Pandas, normalizes the `repository` key and writes
one table per file into metrics.db. Idempotent (tables are replaced).
"""
from __future__ import annotations

import sqlite3

import pandas as pd

from common import DATA_DIR, DB_PATH, get_logger

log = get_logger("consolidate")

CSV_TABLES = [
    "repositories", "commits", "developers", "files", "pull_requests",
    "loc", "structure", "complexity", "tests", "quality_indicators",
]


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        for table in CSV_TABLES:
            path = DATA_DIR / f"{table}.csv"
            if not path.exists():
                log.info("Skip %s (not generated yet)", path.name)
                continue
            try:
                df = pd.read_csv(path)
            except pd.errors.EmptyDataError:
                df = pd.DataFrame()
            if "repository" in df.columns:
                df["repository"] = df["repository"].astype(str).str.strip()
            df.to_sql(table, conn, if_exists="replace", index=False)
            log.info("Loaded %s (%d rows) -> table '%s'",
                     path.name, len(df), table)
        conn.commit()
    finally:
        conn.close()
    log.info("Consolidated database written to %s", DB_PATH)


if __name__ == "__main__":
    main()
