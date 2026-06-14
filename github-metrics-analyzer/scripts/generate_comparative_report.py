"""Phase S8 — Comparative descriptive report (ISO/IEC 25010 security posture).

Builds the comparative statistics required by the AP2 study (deliverable §10.3):
  * per-repository security posture (raw and per-KLOC) — Semgrep, OSV, secrets
  * CWE distribution mapped to ISO/IEC 25010 Security sub-characteristics
  * severity breakdown
  * charts ready for the paper

Pure description from already-collected CSVs. No project is built or executed,
and no metric is fabricated: a repository with no finding shows 0, not an
estimate.

Outputs (reports/):
  comparative_report.md
  charts/security_per_kloc.png
  charts/cwe_distribution.png
  charts/posture_heatmap.png
"""
from __future__ import annotations

import re
from collections import Counter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from common import DATA_DIR, REPORTS_DIR, CHARTS_DIR, get_logger

log = get_logger("report")

# ------------------------------------------------------------------ #
# CWE -> ISO/IEC 25010 Security sub-characteristic mapping
# (per the study's framework table; 25023 provides the measures)
# ------------------------------------------------------------------ #
CWE_TO_SUBCHAR = {
    "CWE-89": "Integridade",   "CWE-78": "Integridade",
    "CWE-502": "Integridade",  "CWE-22": "Integridade",
    "CWE-611": "Integridade",  "CWE-470": "Integridade",
    "CWE-94": "Integridade",   "CWE-79": "Integridade",
    "CWE-200": "Confidencialidade", "CWE-327": "Confidencialidade",
    "CWE-328": "Confidencialidade", "CWE-319": "Confidencialidade",
    "CWE-326": "Confidencialidade", "CWE-1004": "Confidencialidade",
    "CWE-614": "Confidencialidade", "CWE-312": "Confidencialidade",
    "CWE-295": "Autenticidade", "CWE-798": "Autenticidade",
    "CWE-287": "Autenticidade", "CWE-259": "Autenticidade",
}
SUBCHAR_ORDER = ["Integridade", "Confidencialidade", "Autenticidade",
                 "Resistência", "Outras/Não classificada"]


def _short(repo: str) -> str:
    return str(repo).split("/")[-1]


def _safe(name: str) -> pd.DataFrame:
    p = DATA_DIR / name
    if not p.exists():
        log.warning("Missing %s", name)
        return pd.DataFrame()
    return pd.read_csv(p, low_memory=False)


def _cwes(cell: str) -> list[str]:
    return re.findall(r"CWE-\d+", str(cell))


# ------------------------------------------------------------------ #
def build_per_repo(loc, semg, osv, secrets, dataset) -> pd.DataFrame:
    rows = []
    repos = sorted(loc["repository"].unique()) if not loc.empty else []
    for repo in repos:
        kloc = float(loc.loc[loc.repository == repo, "java_code"].sum()) / 1000.0
        jfiles = int(loc.loc[loc.repository == repo, "java_files"].sum())
        findings = int((semg.repository == repo).sum()) if not semg.empty else 0
        # positive .java files come from the ML dataset (unit of analysis)
        if not dataset.empty:
            sub = dataset[dataset.repository == repo]
            files_eval = len(sub)
            pos_files = int(sub["has_security_risk"].sum())
        else:
            files_eval = jfiles
            pos_files = 0
        cves = int(osv.loc[osv.repository == repo, "vulns_direct"].sum()) if not osv.empty else 0
        cvss = float(osv.loc[osv.repository == repo, "avg_cvss"].mean()) if not osv.empty else 0.0
        sec_total = int(secrets.loc[secrets.repository == repo, "total_secrets"].sum()) if not secrets.empty else 0
        rows.append({
            "repositório": _short(repo),
            "arquivos_java": jfiles,
            "KLOC_java": round(kloc, 1),
            "achados_seg": findings,
            "achados_por_KLOC": round(findings / kloc, 2) if kloc else 0.0,
            "arquivos_em_risco": pos_files,
            "pct_risco": round(100 * pos_files / files_eval, 2) if files_eval else 0.0,
            "CVEs_diretos": cves,
            "CVSS_médio": round(cvss, 1) if not np.isnan(cvss) else 0.0,
            "segredos": sec_total,
        })
    df = pd.DataFrame(rows).sort_values("achados_seg", ascending=False)
    return df


def build_cwe_table(semg) -> pd.DataFrame:
    counter: Counter = Counter()
    if not semg.empty:
        for cell in semg["cwe"].dropna():
            for c in _cwes(cell):
                counter[c] += 1
    rows = []
    for cwe, n in counter.most_common():
        rows.append({"CWE": cwe, "achados": n,
                     "sub_característica_25010": CWE_TO_SUBCHAR.get(cwe, "Outras/Não classificada")})
    return pd.DataFrame(rows)


def build_subchar_table(cwe_df, osv) -> pd.DataFrame:
    agg = Counter()
    if not cwe_df.empty:
        for _, r in cwe_df.iterrows():
            agg[r["sub_característica_25010"]] += int(r["achados"])
    # Resistência measured by OSV dependency CVEs
    total_cves = int(osv["vulns_direct"].sum()) if not osv.empty else 0
    agg["Resistência"] += total_cves
    rows = [{"sub_característica (25010)": k,
             "evidências (achados/CVEs)": agg.get(k, 0),
             "fonte": ("OSV-Scanner (dependências)" if k == "Resistência"
                       else "Semgrep (SAST por arquivo)")}
            for k in SUBCHAR_ORDER]
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ #
def chart_per_kloc(per_repo) -> None:
    d = per_repo.sort_values("achados_por_KLOC")
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.barh(d["repositório"], d["achados_por_KLOC"], color="#C62828")
    ax.set_xlabel("Achados de segurança por KLOC (Semgrep)")
    ax.set_title("Densidade de achados de segurança por repositório (normalizada)")
    for i, v in enumerate(d["achados_por_KLOC"]):
        ax.text(v + 0.01, i, f"{v:.2f}", va="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(CHARTS_DIR / "security_per_kloc.png", dpi=150)
    plt.close(fig)
    log.info("Saved security_per_kloc.png")


def chart_cwe(cwe_df) -> None:
    if cwe_df.empty:
        return
    d = cwe_df.head(12).iloc[::-1]
    colors = {"Integridade": "#C62828", "Confidencialidade": "#1565C0",
              "Autenticidade": "#6A1B9A", "Resistência": "#2E7D32",
              "Outras/Não classificada": "#757575"}
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.barh(d["CWE"], d["achados"],
            color=[colors.get(s, "#757575") for s in d["sub_característica_25010"]])
    ax.set_xlabel("Nº de achados")
    ax.set_title("Distribuição de CWE (cor = sub-característica ISO/IEC 25010)")
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in colors.values()]
    ax.legend(handles, colors.keys(), fontsize=8, loc="lower right")
    fig.tight_layout()
    fig.savefig(CHARTS_DIR / "cwe_distribution.png", dpi=150)
    plt.close(fig)
    log.info("Saved cwe_distribution.png")


def chart_heatmap(per_repo) -> None:
    cols = ["achados_por_KLOC", "pct_risco", "CVEs_diretos", "segredos"]
    m = per_repo.set_index("repositório")[cols].astype(float)
    # normalise each column to 0..1 for visual comparison
    norm = (m - m.min()) / (m.max() - m.min()).replace(0, 1)
    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(norm.values, cmap="Reds", aspect="auto")
    ax.set_xticks(range(len(cols)))
    ax.set_xticklabels(["ach/KLOC", "% risco", "CVEs", "segredos"], rotation=20)
    ax.set_yticks(range(len(norm.index)))
    ax.set_yticklabels(norm.index, fontsize=8)
    for i in range(len(norm.index)):
        for j in range(len(cols)):
            ax.text(j, i, f"{m.values[i, j]:.1f}", ha="center", va="center",
                    fontsize=7, color="black")
    ax.set_title("Postura de segurança (valores brutos; cor = intensidade relativa)")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="intensidade (normalizada)")
    fig.tight_layout()
    fig.savefig(CHARTS_DIR / "posture_heatmap.png", dpi=150)
    plt.close(fig)
    log.info("Saved posture_heatmap.png")


# ------------------------------------------------------------------ #
def _md_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_(sem dados)_\n"
    head = "| " + " | ".join(df.columns) + " |\n"
    sep = "| " + " | ".join(["---"] * len(df.columns)) + " |\n"
    body = "".join("| " + " | ".join(str(v) for v in row) + " |\n"
                   for row in df.itertuples(index=False))
    return head + sep + body


def main() -> None:
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    loc = _safe("loc.csv")
    semg = _safe("semgrep_findings.csv")
    osv = _safe("osv_summary.csv")
    secrets = _safe("secrets_summary.csv")
    dataset = _safe("security_dataset.csv")
    ml = pd.read_csv(REPORTS_DIR / "ml_results.csv") if (REPORTS_DIR / "ml_results.csv").exists() else pd.DataFrame()

    per_repo = build_per_repo(loc, semg, osv, secrets, dataset)
    cwe_df = build_cwe_table(semg)
    subchar = build_subchar_table(cwe_df, osv)

    chart_per_kloc(per_repo)
    chart_cwe(cwe_df)
    chart_heatmap(per_repo)

    # severity breakdown
    sev = (semg["severity"].str.upper().value_counts().rename_axis("severidade")
           .reset_index(name="achados") if not semg.empty else pd.DataFrame())

    n_files = len(dataset)
    n_pos = int(dataset["has_security_risk"].sum()) if not dataset.empty else 0
    datawave_eco = {"datawave", "datawave-query-service",
                    "datawave-audit-service", "datawave-authorization-service"}

    md = []
    md.append("# Relatório comparativo — Postura de segurança (ISO/IEC 25010)\n")
    md.append("Estudo estático (apenas clone, sem build) de 10 repositórios Java da "
              "organização `NationalSecurityAgency`. Valores **brutos e normalizados "
              "por KLOC**. Métrica não coletável aparece como ausente/zero — nunca estimada.\n")
    md.append(f"\n**Unidade de análise:** arquivo `.java`. **Total:** {n_files} arquivos; "
              f"**{n_pos} com risco de segurança** ({100*n_pos/max(1,n_files):.2f}%).\n")

    md.append("\n## 1. Postura por repositório (bruto + por KLOC)\n")
    md.append(_md_table(per_repo))
    md.append("\n> Três repositórios (`datawave`, `datawave-query-service`, "
              "`datawave-audit-service`, `datawave-authorization-service`) pertencem ao "
              "ecossistema **DataWave** — variável de confusão / limitação de validade "
              "externa (Seção de limitações).\n")

    md.append("\n## 2. Distribuição de CWE → sub-característica ISO/IEC 25010\n")
    md.append(_md_table(cwe_df))

    md.append("\n## 3. Cobertura das sub-características de Segurança (25010)\n")
    md.append(_md_table(subchar))
    md.append("\n> **Não-repúdio** e **Responsabilização** não são mensuráveis por "
              "SAST/SCA estática → discussão qualitativa/limitação. **Safety** (25010:2023) "
              "não é medida por nenhuma ferramenta deste estudo.\n")

    if not sev.empty:
        md.append("\n## 4. Severidade dos achados (Semgrep)\n")
        md.append(_md_table(sev))

    if not ml.empty:
        md.append("\n## 5. Predição por ML (GroupKFold por repositório)\n")
        md.append(_md_table(ml))
        md.append("\n> Avaliação liderada por **ROC-AUC/Recall/F1** (não accuracy), dado o "
                  "forte desbalanceamento. Features: complexidade (lizard), OO (CK) "
                  "e processo (PyDriller) — **nenhuma derivada do alvo** "
                  "(anti-vazamento).\n")

    md.append("\n## Figuras\n")
    md.append("- `charts/security_per_kloc.png` — densidade de achados por KLOC.\n")
    md.append("- `charts/cwe_distribution.png` — CWE por sub-característica 25010.\n")
    md.append("- `charts/posture_heatmap.png` — mapa comparativo da postura.\n")
    md.append("- `charts/roc_curves.png`, `charts/model_comparison.png`, "
              "`charts/feature_importance_rf.png`, `charts/shap_summary.png` — ML.\n")

    out = REPORTS_DIR / "comparative_report.md"
    out.write_text("".join(md), encoding="utf-8")
    log.info("Wrote %s", out)

    # also persist the per-repo table as CSV for the paper/tables
    per_repo.to_csv(REPORTS_DIR / "comparative_per_repo.csv", index=False)
    cwe_df.to_csv(REPORTS_DIR / "comparative_cwe.csv", index=False)
    log.info("Wrote comparative_per_repo.csv and comparative_cwe.csv")


if __name__ == "__main__":
    main()
