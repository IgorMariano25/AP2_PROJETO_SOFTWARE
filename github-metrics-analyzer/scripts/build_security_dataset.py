"""Phase S6 - Merge all per-file metrics into the ML dataset.

Unit of analysis: each .java file across all 10 repositories.

Sources merged:
  data/semgrep_findings.csv   → target: has_security_risk (binary)
  data/complexity.csv         → CCN (method-level → file-level aggregates)
  data/ck_metrics.csv         → CK OO metrics per file (canonical OO source)
  data/pydriller_metrics.csv  → process metrics per file
  data/loc.csv                → lines of code per repo (used for normalisation)

ANTI-LEAKAGE RULE: no security-derived metric may appear as a feature.
The only use of semgrep_findings.csv is to build the binary target.

Output:
  data/security_dataset.csv — one row per (repository, file) pair
  data/dataset_dictionary.md — column documentation
"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

import pandas as pd

from common import DATA_DIR, get_logger

log = get_logger("dataset")

TARGET_COL = "has_security_risk"


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _safe_load(name: str) -> pd.DataFrame:
    path = DATA_DIR / name
    if not path.exists():
        log.warning("Missing %s — skipping", name)
        return pd.DataFrame()
    df = pd.read_csv(path, low_memory=False)
    log.info("Loaded %s: %d rows, %d cols", name, len(df), len(df.columns))
    return df


def _normalise_path(p: str) -> str:
    """Normalise file path separators for join consistency."""
    return p.replace("\\", "/").lstrip("./")


# ------------------------------------------------------------------ #
# Build target: has_security_risk from semgrep findings
# ------------------------------------------------------------------ #

def build_target(findings: pd.DataFrame) -> pd.DataFrame:
    if findings.empty:
        return pd.DataFrame(columns=["repository", "file", TARGET_COL])
    findings = findings.copy()
    findings["file"] = findings["file"].astype(str).apply(_normalise_path)
    target = (
        findings.groupby(["repository", "file"])
        .size()
        .reset_index(name="finding_count")
    )
    target[TARGET_COL] = 1
    return target[["repository", "file", TARGET_COL]]


# ------------------------------------------------------------------ #
# Aggregate complexity.csv (method → file)
# ------------------------------------------------------------------ #

def aggregate_complexity(complexity: pd.DataFrame) -> pd.DataFrame:
    if complexity.empty:
        return pd.DataFrame()
    c = complexity.copy()
    c["file"] = c["file"].astype(str).apply(_normalise_path)
    agg = c.groupby(["repository", "file"]).agg(
        ccn_max=("ccn", "max"),
        ccn_mean=("ccn", "mean"),
        ccn_sum=("ccn", "sum"),
        nloc_sum=("nloc", "sum"),
        num_methods_lizard=("method", "count"),
        tokens_sum=("tokens", "sum"),
        params_max=("parameters", "max"),
    ).reset_index()
    return agg


# ------------------------------------------------------------------ #
# CK metrics (already file-level)
# ------------------------------------------------------------------ #

def load_ck(ck: pd.DataFrame) -> pd.DataFrame:
    if ck.empty:
        return pd.DataFrame()
    ck = ck.copy()
    ck["file"] = ck["file"].astype(str).apply(_normalise_path)
    return ck


# ------------------------------------------------------------------ #
# PyDriller process metrics (already file-level)
# ------------------------------------------------------------------ #

def load_pydriller(pyd: pd.DataFrame) -> pd.DataFrame:
    if pyd.empty:
        return pd.DataFrame()
    pyd = pyd.copy()
    pyd["file"] = pyd["file"].astype(str).apply(_normalise_path)
    return pyd


# ------------------------------------------------------------------ #
# LOC per file (from loc.csv — repo-level; used for normalisation)
# ------------------------------------------------------------------ #

def load_loc(loc: pd.DataFrame) -> pd.DataFrame:
    if loc.empty:
        return pd.DataFrame()
    # loc.csv is repo-level; we extract Java LOC for normalisation downstream
    return loc[["repository", "java_loc"]].copy() if "java_loc" in loc.columns else pd.DataFrame()


# ------------------------------------------------------------------ #
# Main
# ------------------------------------------------------------------ #

def main() -> None:
    # 1. Load raw CSVs
    findings  = _safe_load("semgrep_findings.csv")
    complexity = _safe_load("complexity.csv")
    ck         = _safe_load("ck_metrics.csv")
    pydriller  = _safe_load("pydriller_metrics.csv")
    loc        = _safe_load("loc.csv")

    # 2. Build base: target
    target = build_target(findings)

    # 3. Build feature tables
    feat_complexity = aggregate_complexity(complexity)
    feat_ck         = load_ck(ck)
    feat_process    = load_pydriller(pydriller)

    # 4. Determine universe of Java files from available metrics
    file_sets = []
    for df, name in [
        (feat_complexity, "complexity"),
        (feat_ck, "ck"),
        (feat_process, "pydriller"),
    ]:
        if df is not None and not df.empty and "file" in df.columns:
            file_sets.append(df[["repository", "file"]])

    if not file_sets:
        log.error("No file-level feature data available. Run metric collection first.")
        return

    universe = pd.concat(file_sets).drop_duplicates(subset=["repository", "file"])
    log.info("Universe: %d (repository, file) pairs", len(universe))

    # 5. Merge all features into universe
    df = universe.copy()

    merge_kw = {"on": ["repository", "file"], "how": "left"}

    if not target.empty:
        df = df.merge(target, **merge_kw)
    else:
        df[TARGET_COL] = 0

    if feat_complexity is not None and not feat_complexity.empty:
        df = df.merge(feat_complexity, **merge_kw)

    if feat_ck is not None and not feat_ck.empty:
        df = df.merge(feat_ck, **merge_kw)

    if feat_process is not None and not feat_process.empty:
        df = df.merge(feat_process, **merge_kw)

    # 6. Fill target NaN → 0 (file with no finding = not risky)
    df[TARGET_COL] = df[TARGET_COL].fillna(0).astype(int)

    # 7. Drop rows where ALL numeric features are NaN (files with zero data)
    feature_cols = [c for c in df.columns
                    if c not in ("repository", "file", TARGET_COL)]
    before = len(df)
    df = df.dropna(subset=feature_cols, how="all")
    log.info("Dropped %d rows with all-NaN features (kept %d)", before - len(df), len(df))

    # 8. Fill remaining NaN with 0
    df[feature_cols] = df[feature_cols].fillna(0)

    # 9. Basic stats
    pos = int(df[TARGET_COL].sum())
    neg = len(df) - pos
    log.info("Dataset: %d files  |  positive (risk)=%d (%.1f%%)  negative=%d",
             len(df), pos, 100 * pos / max(1, len(df)), neg)
    if pos == 0:
        log.warning("ZERO positive labels!  Check that semgrep_findings.csv is populated.")

    # 10. Write
    out = DATA_DIR / "security_dataset.csv"
    df.to_csv(out, index=False)
    log.info("Wrote %s (%d rows × %d cols)", out.name, len(df), len(df.columns))

    _write_dictionary(df)


# ------------------------------------------------------------------ #
# Data dictionary
# ------------------------------------------------------------------ #

_DICT = {
    "repository": "GitHub full name of the repository (owner/repo)",
    "file": "Relative path of the .java file within the repository",
    TARGET_COL: "Binary target (ISO 25010 Segurança): 1 = file has ≥1 Semgrep security finding; 0 = no finding",
    # Complexity (lizard)
    "ccn_max": "Maximum cyclomatic complexity (CCN) among all methods in the file",
    "ccn_mean": "Mean CCN across all methods",
    "ccn_sum": "Sum of CCN across all methods (≈ WMC proxy without class weighting)",
    "nloc_sum": "Total non-comment lines of code across all methods",
    "num_methods_lizard": "Number of methods detected by lizard",
    "tokens_sum": "Total token count across all methods",
    "params_max": "Maximum parameter count across all methods",
    # CK (Maurício Aniche)
    "wmc": "Weighted Methods per Class (sum across classes in file) [ISO 25010 Manutenibilidade]",
    "dit": "Depth of Inheritance Tree (max across classes in file)",
    "noc": "Number of Children (max in file)",
    "cbo": "Coupling Between Objects (max in file) [ISO 25010 Manutenibilidade]",
    "rfc": "Response For a Class (sum across classes) [ISO 25010 Confiabilidade]",
    "lcom": "Lack of Cohesion in Methods (max in file)",
    "lcom_star": "Normalised LCOM* (max in file)",
    "num_methods": "Total methods per file (CK count)",
    "num_static_methods": "Static methods per file",
    "num_fields": "Total fields per file (CK)",
    "num_static_fields": "Static fields per file",
    "tcc": "Tight Class Cohesion (max in file) [ISO 25010 Manutenibilidade]",
    "lcc": "Loose Class Cohesion (max in file)",
    "num_classes": "Number of top-level class declarations (CK)",
    # PyDriller process
    "commits": "Number of commits that modified this file [ISO 25010 Manutenibilidade]",
    "distinct_authors": "Number of distinct developers who touched this file",
    "lines_added": "Total lines added across all commits",
    "lines_removed": "Total lines removed across all commits",
    "churn": "lines_added + lines_removed (total code churn)",
    "file_age_days": "Days between first and last commit of the file",
    "days_since_change": "Days since the most recent commit to the file",
}


def _write_dictionary(df: pd.DataFrame) -> None:
    out = DATA_DIR / "dataset_dictionary.md"
    lines = ["# Security Dataset — Column Dictionary\n",
             "| Column | Type | Description | ISO 25010 mapping |\n",
             "|--------|------|-------------|------------------|\n"]
    for col in df.columns:
        dtype = str(df[col].dtype)
        desc = _DICT.get(col, "—")
        # Infer ISO mapping from description
        iso = ""
        if "Manutenibilidade" in desc:
            iso = "Manutenibilidade"
        elif "Confiabilidade" in desc:
            iso = "Confiabilidade"
        elif "Segurança" in desc or "25010" in desc:
            iso = "Segurança"
        lines.append(f"| `{col}` | {dtype} | {desc} | {iso} |\n")
    out.write_text("".join(lines), encoding="utf-8")
    log.info("Wrote %s", out.name)


if __name__ == "__main__":
    main()
