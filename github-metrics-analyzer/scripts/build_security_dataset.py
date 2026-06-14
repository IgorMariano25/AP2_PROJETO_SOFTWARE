"""Phase S6 - Merge all per-file metrics into the ML dataset.

Unit of analysis: each .java file across all 10 repositories.

Sources merged:
  data/semgrep_findings.csv   → target (SAST #1)
  data/codeql_findings.csv    → target (SAST #2, optional) — UNION with Semgrep
  data/sonarqube.csv          → structural features (CANONICAL when present)
  data/complexity.csv         → lizard CCN — structural FALLBACK if no SonarQube
  data/ck_metrics.csv         → CK OO metrics per file (canonical OO source)
  data/pydriller_metrics.csv  → process metrics per file
  data/loc.csv                → lines of code per repo (used for normalisation)

Target: has_security_risk = 1 if a file is flagged by Semgrep OR CodeQL (union;
maximises recall — security false-negatives are the worst error, §8.4). The
per-tool counts (n_semgrep, n_codeql) are written for transparency/agreement
analysis but are EXCLUDED from ML features (see ml_security_pipeline SKIP_COLS).

Structural source: SonarQube is canonical (complexity, cognitive complexity,
duplication, code smells, comments). To honour the "one source per dimension"
rule, the lizard CCN aggregates are used ONLY as a fallback when sonarqube.csv
is absent/empty — never both at once (avoids multicollinearity).

ANTI-LEAKAGE RULE: no security-derived metric may appear as a feature.
semgrep/codeql findings are used ONLY to build the target and its agreement
columns; SonarQube security measures are excluded by metric selection.

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

# Identifier + label + target-derived columns. Never ML features (anti-leakage);
# ml_security_pipeline.SKIP_COLS must stay in sync with this set.
NONFEATURE_COLS = ("repository", "file", TARGET_COL, "n_semgrep", "n_codeql")


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
# Build target: has_security_risk = Semgrep ∪ CodeQL (per-file)
# ------------------------------------------------------------------ #

def _per_tool_counts(findings: pd.DataFrame, col: str) -> pd.DataFrame:
    """Count findings per (repository, file) into a named column."""
    if findings is None or findings.empty:
        return pd.DataFrame(columns=["repository", "file", col])
    f = findings.copy()
    f["file"] = f["file"].astype(str).apply(_normalise_path)
    return (f.groupby(["repository", "file"]).size()
            .reset_index(name=col))


def build_target(semgrep: pd.DataFrame, codeql: pd.DataFrame) -> pd.DataFrame:
    """Union target with transparency columns (n_semgrep, n_codeql).

    A file is risky if EITHER SAST tool flags it. The per-tool counts are kept
    for agreement analysis only — ml_security_pipeline excludes them.
    """
    sem = _per_tool_counts(semgrep, "n_semgrep")
    cq = _per_tool_counts(codeql, "n_codeql")
    target = sem.merge(cq, on=["repository", "file"], how="outer")
    if target.empty:
        return pd.DataFrame(columns=["repository", "file", "n_semgrep",
                                     "n_codeql", TARGET_COL])
    target["n_semgrep"] = target["n_semgrep"].fillna(0).astype(int)
    target["n_codeql"] = target["n_codeql"].fillna(0).astype(int)
    target[TARGET_COL] = ((target["n_semgrep"] + target["n_codeql"]) > 0).astype(int)
    return target[["repository", "file", "n_semgrep", "n_codeql", TARGET_COL]]


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
# SonarQube structural metrics (canonical; already file-level)
# ------------------------------------------------------------------ #
# Security-derived measures are intentionally NOT collected (see
# collect_sonarqube_metrics) so nothing here can leak into the target.

def load_sonarqube(sonar: pd.DataFrame) -> pd.DataFrame:
    if sonar.empty:
        return pd.DataFrame()
    s = sonar.copy()
    s["file"] = s["file"].astype(str).apply(_normalise_path)
    # Coerce metric columns to numeric (the Web API returns strings).
    for c in s.columns:
        if c not in ("repository", "file"):
            s[c] = pd.to_numeric(s[c], errors="coerce")
    # Prefix to make the source explicit in the dataset/dictionary.
    s = s.rename(columns={c: f"sonar_{c}" for c in s.columns
                          if c not in ("repository", "file")})
    return s


def structural_features(sonar: pd.DataFrame, complexity: pd.DataFrame
                        ) -> tuple[pd.DataFrame, str]:
    """Return the canonical structural feature table and its source label.

    SonarQube wins when present (richer, prompt-canonical). lizard CCN is the
    fallback so the pipeline still runs offline — but never both at once.
    """
    sonar_feat = load_sonarqube(sonar)
    if not sonar_feat.empty:
        return sonar_feat, "sonarqube"
    return aggregate_complexity(complexity), "lizard (fallback)"


# ------------------------------------------------------------------ #
# Main
# ------------------------------------------------------------------ #

def _build_universe(feature_tables: list) -> pd.DataFrame | None:
    """Distinct (repository, file) pairs across all non-empty feature tables."""
    file_sets = [t[["repository", "file"]] for t in feature_tables
                 if t is not None and not t.empty and "file" in t.columns]
    if not file_sets:
        return None
    return pd.concat(file_sets).drop_duplicates(subset=["repository", "file"]).copy()


def main() -> None:
    # 1. Load raw CSVs
    semgrep    = _safe_load("semgrep_findings.csv")
    codeql     = _safe_load("codeql_findings.csv")
    sonar      = _safe_load("sonarqube.csv")
    complexity = _safe_load("complexity.csv")
    ck         = _safe_load("ck_metrics.csv")
    pydriller  = _safe_load("pydriller_metrics.csv")
    loc        = _safe_load("loc.csv")

    # 2. Build base: union target (Semgrep ∪ CodeQL) + per-tool counts
    target = build_target(semgrep, codeql)

    # 3. Build feature tables. Structural source is SonarQube when available,
    #    else lizard CCN — one source per dimension (no double-count).
    feat_structural, struct_src = structural_features(sonar, complexity)
    feat_ck         = load_ck(ck)
    feat_process    = load_pydriller(pydriller)
    log.info("Structural feature source: %s", struct_src)

    # 4. Universe of Java files = union of all file-level feature tables.
    feature_tables = [feat_structural, feat_ck, feat_process]
    df = _build_universe(feature_tables)
    if df is None:
        log.error("No file-level feature data available. Run metric collection first.")
        return
    log.info("Universe: %d (repository, file) pairs", len(df))

    # 5. Merge target + features into the universe
    merge_kw = {"on": ["repository", "file"], "how": "left"}
    if not target.empty:
        df = df.merge(target, **merge_kw)
    else:
        df[TARGET_COL] = 0
    for feat in feature_tables:
        if feat is not None and not feat.empty:
            df = df.merge(feat, **merge_kw)

    # 6. Fill target + per-tool counts NaN → 0 (file with no finding = not risky)
    for col in (TARGET_COL, "n_semgrep", "n_codeql"):
        if col in df.columns:
            df[col] = df[col].fillna(0).astype(int)

    # 7. Drop rows where ALL numeric features are NaN (files with zero data)
    feature_cols = [c for c in df.columns if c not in NONFEATURE_COLS]
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
    TARGET_COL: "Binary target (ISO 25010 Segurança): 1 = file flagged by Semgrep OR CodeQL (union); 0 = no finding",
    # Per-tool finding counts — transparency/agreement only, NOT ML features
    "n_semgrep": "Number of Semgrep security findings in the file (descriptive; excluded from ML)",
    "n_codeql": "Number of CodeQL security findings in the file (descriptive; excluded from ML)",
    # SonarQube structural metrics (canonical source when present)
    "sonar_ncloc": "Non-comment lines of code (SonarQube) [Manutenibilidade]",
    "sonar_complexity": "Cyclomatic complexity (SonarQube) [Manutenibilidade]",
    "sonar_cognitive_complexity": "Cognitive complexity (SonarQube) [Manutenibilidade]",
    "sonar_duplicated_lines_density": "% duplicated lines (SonarQube) [Manutenibilidade]",
    "sonar_comment_lines_density": "% comment lines (SonarQube) [Manutenibilidade]",
    "sonar_code_smells": "Code smells (SonarQube, source-only → partial) [Manutenibilidade]",
    "sonar_violations": "Total rule violations (SonarQube, source-only → partial)",
    "sonar_sqale_index": "Technical-debt remediation effort, minutes (SonarQube)",
    # Complexity (lizard — fallback structural source when SonarQube absent)
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
