"""Phase 10 - Compute derived quality indicators.

Reads the per-source CSVs and produces:

  * data/quality_indicators.csv  -> one row per repository
  * data/hotspots.csv            -> per-file hotspot scores (commits x complexity)

Indicators: project activity, contribution distribution, concentration risk,
average complexity, testability, maintainability proxy, modularity and PR health.
"""
from __future__ import annotations

import pandas as pd

from common import DATA_DIR, get_logger

log = get_logger("indicators")


def _read(name: str) -> pd.DataFrame:
    path = DATA_DIR / name
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def top_n_share(group: pd.DataFrame, n: int = 5) -> float:
    total = group["commits"].sum()
    if total == 0:
        return 0.0
    top = group.nlargest(n, "commits")["commits"].sum()
    return round(100 * top / total, 2)


def compute_hotspots(files: pd.DataFrame, complexity: pd.DataFrame) -> pd.DataFrame:
    if files.empty:
        return pd.DataFrame()

    # Average CCN per file (path normalized to forward slashes)
    file_ccn = pd.DataFrame()
    if not complexity.empty:
        file_ccn = (complexity.groupby(["repository", "file"])["ccn"]
                    .mean().reset_index().rename(columns={"ccn": "avg_ccn"}))

    merged = files.copy()
    merged["file"] = merged["file"].astype(str)
    if not file_ccn.empty:
        merged = merged.merge(file_ccn, on=["repository", "file"], how="left")
    else:
        merged["avg_ccn"] = 0.0
    merged["avg_ccn"] = merged["avg_ccn"].fillna(0.0)
    merged["hotspot_score"] = merged["commits"] * merged["avg_ccn"]
    merged = merged.sort_values("hotspot_score", ascending=False)
    return merged[["repository", "file", "commits", "avg_ccn", "hotspot_score"]]


def main() -> None:
    repositories = _read("repositories.csv")
    commits = _read("commits.csv")
    developers = _read("developers.csv")
    files = _read("files.csv")
    prs = _read("pull_requests.csv")
    loc = _read("loc.csv")
    structure = _read("structure.csv")
    complexity = _read("complexity.csv")
    tests = _read("tests.csv")

    # Use the union of all known repositories.
    repos = set()
    for df in (repositories.rename(columns={"full_name": "repository"})
               if "full_name" in repositories.columns else repositories,
               commits, developers, loc, tests, structure):
        if not df.empty and "repository" in df.columns:
            repos.update(df["repository"].astype(str).unique())

    rows = []
    for repo in sorted(repos):
        row: dict = {"repository": repo}

        # --- Repo metadata / activity ------------------------------------ #
        meta = pd.DataFrame()
        if not repositories.empty:
            col = "full_name" if "full_name" in repositories.columns else "repository"
            meta = repositories[repositories[col].astype(str) == repo]
        stars = int(meta["stars"].iloc[0]) if not meta.empty and "stars" in meta else 0
        forks = int(meta["forks"].iloc[0]) if not meta.empty and "forks" in meta else 0

        c = commits[commits["repository"] == repo] if not commits.empty else pd.DataFrame()
        total_commits = int(c["total_commits"].iloc[0]) if not c.empty else 0
        active_days = int(c["distinct_active_days"].iloc[0]) if not c.empty and "distinct_active_days" in c else 0

        # --- Contribution distribution / concentration risk -------------- #
        dev = developers[developers["repository"] == repo] if not developers.empty else pd.DataFrame()
        n_devs = len(dev)
        top5 = top_n_share(dev, 5) if not dev.empty else 0.0
        concentration_risk = "high" if top5 >= 80 else "medium" if top5 >= 60 else "low"

        # --- Complexity / maintainability -------------------------------- #
        comp = complexity[complexity["repository"] == repo] if not complexity.empty else pd.DataFrame()
        avg_ccn = round(comp["ccn"].mean(), 2) if not comp.empty else 0.0
        avg_method_nloc = round(comp["nloc"].mean(), 2) if not comp.empty else 0.0
        avg_params = round(comp["parameters"].mean(), 2) if not comp.empty else 0.0
        max_ccn = int(comp["ccn"].max()) if not comp.empty else 0

        # --- Structure / modularity -------------------------------------- #
        st = structure[structure["repository"] == repo] if not structure.empty else pd.DataFrame()
        n_classes = int((st["kind"] == "class").sum()) if not st.empty else 0
        n_interfaces = int((st["kind"] == "interface").sum()) if not st.empty else 0
        n_methods = int(st["methods"].sum()) if not st.empty else 0
        n_inheritance = int((st["extends"].astype(str).str.len() > 0).sum()) if not st.empty else 0

        # --- Tests / testability ----------------------------------------- #
        t = tests[tests["repository"] == repo] if not tests.empty else pd.DataFrame()
        test_methods = int(t["test_methods"].iloc[0]) if not t.empty else 0
        testability = round(test_methods / n_methods, 4) if n_methods else 0.0

        # --- LOC ---------------------------------------------------------- #
        l = loc[loc["repository"] == repo] if not loc.empty else pd.DataFrame()
        total_loc = int(l["code"].iloc[0]) if not l.empty and "code" in l else 0

        # --- PR health ---------------------------------------------------- #
        p = prs[prs["repository"] == repo] if not prs.empty else pd.DataFrame()
        pr_open = int((p["state"] == "open").sum()) if not p.empty else 0
        pr_closed = int((p["state"].isin(["closed", "merged"])).sum()) if not p.empty else 0
        avg_commits_per_pr = round(pd.to_numeric(p["commits"], errors="coerce").mean(), 2) if not p.empty else 0.0
        avg_close_hours = round(pd.to_numeric(p["hours_to_close"], errors="coerce").mean(), 2) if not p.empty else 0.0

        # --- Composite activity score ------------------------------------ #
        activity_score = total_commits + active_days * 5 + (pr_open + pr_closed)

        row.update({
            "stars": stars,
            "forks": forks,
            "total_commits": total_commits,
            "active_days": active_days,
            "contributors": n_devs,
            "top5_commit_share_pct": top5,
            "concentration_risk": concentration_risk,
            "total_loc": total_loc,
            "avg_ccn": avg_ccn,
            "max_ccn": max_ccn,
            "avg_method_nloc": avg_method_nloc,
            "avg_method_params": avg_params,
            "classes": n_classes,
            "interfaces": n_interfaces,
            "methods": n_methods,
            "inheritance_links": n_inheritance,
            "test_methods": test_methods,
            "testability": testability,
            "pr_open": pr_open,
            "pr_closed": pr_closed,
            "avg_commits_per_pr": avg_commits_per_pr,
            "avg_pr_close_hours": avg_close_hours,
            "activity_score": activity_score,
        })
        rows.append(row)

    indicators = pd.DataFrame(rows)
    out = DATA_DIR / "quality_indicators.csv"
    indicators.to_csv(out, index=False, encoding="utf-8")
    log.info("Wrote %d rows to %s", len(indicators), out.name)

    hotspots = compute_hotspots(files, complexity)
    if not hotspots.empty:
        hotspots.head(500).to_csv(DATA_DIR / "hotspots.csv", index=False,
                                  encoding="utf-8")
        log.info("Wrote top hotspots to hotspots.csv")


if __name__ == "__main__":
    main()
