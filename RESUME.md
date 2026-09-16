# RESUME.md — Contexto do Projeto (AP2 — Engenharia de Software)

> Documento de contexto destinado a **assistentes de IA**. Resume objetivo,
> arquitetura, metodologia, ferramentas, dados, ML e convenções do projeto,
> para que outro agente compreenda rapidamente o repositório sem precisar
> reexplorar tudo. Fonte: leitura real dos arquivos do workspace
> (`AP2_Trabalho_Final.md`, `github-metrics-analyzer/`, `Artigo/`).

---

## 1. O que é o projeto

Trabalho acadêmico (AP2) que aplica **Engenharia de Software + Ciência de Dados +
Machine Learning** à **mineração de repositórios de código-fonte** (MSR).

**Problema escolhido:** prever quais arquivos `.java` são **propensos a risco de
segurança**, a partir de métricas de qualidade/estrutura/processo, ancorando tudo
na norma **ISO/IEC 25010 / 25023**.

**Corpus:** 10 repositórios Java reais da organização `NationalSecurityAgency`
(NSA) no GitHub (ex.: `ghidra`, `datawave`, `emissary`, `timely`, `lemongrenade`,
`fractalrabbit`, `rank-based-linkage` e serviços do ecossistema DataWave).

**Princípio central (crítico):** análise **100% estática** sobre o código-fonte
clonado. **Nenhum projeto é compilado, buildado ou executado.** Isso condiciona
todas as escolhas de ferramenta (ex.: CodeQL `--build-mode=none`, SonarScanner
source-only).

O trabalho tem 3 entregas: (1) extração de dados/métricas, (2) pipeline de ML,
(3) artigo científico no padrão SBC.

---

## 2. Estrutura do workspace

```
AP2-Projeto-ES/
├── AP2_Trabalho_Final.md          # Enunciado oficial do trabalho
├── RESUME.md                      # (este arquivo)
├── Artigo/                        # Artigo científico SBC (LaTeX)
│   ├── main.tex                   # Corpo do artigo com números reais
│   ├── referencias.bib            # Bibliografia (obras reais)
│   ├── sbc-template.sty / sbc.bst # Estilo SBC
│   └── figuras/                   # Figuras do artigo
└── github-metrics-analyzer/       # Pipeline de coleta + ML (núcleo do projeto)
    ├── README.md                  # Documentação principal do pipeline
    ├── resumo.md                  # Resumo técnico detalhado (versões, decisões)
    ├── TOOLS_VERSIONS.md          # Versões exatas usadas
    ├── requirements.txt           # Dependências Python
    ├── repos.txt                  # Lista owner/repo
    ├── scripts/                   # Uma fase por arquivo + common.py + run_all.py
    ├── data/                      # CSVs de saída + dataset final + dicionário
    ├── reports/                   # Relatório comparativo + resultados ML + charts/
    ├── repos/                     # Clones git (gerado, sem build)
    ├── developer-tools/           # Binários pesados (gitignored): CK, CodeQL, gitleaks, sonar-scanner
    └── tools/                     # Temporários do CK
```

---

## 3. Metodologia — "uma fonte por dimensão"

Cada dimensão de análise tem **uma única ferramenta canônica**, para evitar
multicolinearidade e não contaminar o ranking de importância de features (o
resultado que liga métricas às sub-características da ISO 25010).

| Dimensão | Ferramenta canônica | Fallback | ISO 25010 |
|---|---|---|---|
| **SAST (alvo do ML)** | **Semgrep ∪ CodeQL** (união) | — | Segurança |
| Estrutura / complexidade | **SonarQube** (Web API) | lizard (offline) | Manutenibilidade |
| Métricas OO | **CK** (Maurício Aniche) | — | Manutenibilidade |
| Processo (git) | **PyDriller** | — | Manutenibilidade |
| SCA (dependências) | **OSV API** | — | Segurança > Resistência |
| Segredos expostos | **Gitleaks + detect-secrets** (união dedup) | — | Segurança > Confidencialidade |
| Linhas de código | **cloc** | contador Python | normalização KLOC |

**Regras metodológicas importantes:**
- **Alvo = união Semgrep ∪ CodeQL:** arquivo é positivo (`has_security_risk=1`)
  se *qualquer* das duas SASTs o sinaliza. Maximiza recall (em segurança,
  falso-negativo é o pior erro).
- **Anti-vazamento:** `n_semgrep` e `n_codeql` entram no dataset apenas como
  descritivo e são **excluídos das features do ML** (derivam do alvo).
- **SonarQube NÃO é oráculo de segurança:** sem bytecode, regras de segurança
  não disparam; ele fornece apenas estrutura/manutenibilidade.
- **SonarQube OU lizard**, nunca ambos (fallback quando `sonarqube.csv` ausente).
- **Segredos e OSV** são descritivos (não são feature nem alvo do ML).
- **Degradação graciosa:** se uma ferramenta pesada faltar, a fase grava saída
  vazia e o pipeline continua.

---

## 4. Pipeline de execução

Orquestrado por `scripts/run_all.py` (lista `PHASES`). Cada fase é um módulo
independente com `main()`; falhas são logadas e não abortam o restante (exceto
`--strict`). Todos compartilham `scripts/common.py` (caminhos absolutos, logging,
`.env`, resolução de ferramentas, GitHub API com rate-limit/backoff).

```
clone ──► repos/ (clones git, sem build)
   ├─► loc          → data/loc.csv                 (normalização KLOC)
   ├─► complexity   → data/complexity.csv          (lizard; fallback estrutural)
   ├─► sonarqube    → data/sonarqube.csv           (estrutural canônico)
   ├─► semgrep      → data/semgrep_findings.csv     ┐ alvo do ML
   ├─► codeql       → data/codeql_findings.csv      ┘ (união)
   ├─► pydriller    → data/pydriller_metrics.csv    (processo, feature)
   ├─► ck           → data/ck_metrics.csv           (OO, feature)
   ├─► osv          → data/osv_*.csv                (descritivo SCA)
   └─► secrets      → data/secrets_*.csv            (descritivo)
                            │
   dataset ◄──────────────── (junta todos)  → data/security_dataset.csv + dataset_dictionary.md
                            │
   ml ◄───────────────────── (lê só security_dataset.csv) → reports/ml_results.csv, ml_confusions.csv, charts/*.png
                            │
   report ◄───────────────── → reports/comparative_report.md + charts/*.png
```

**Dependências reais:** `clone` primeiro; as 9 coletas são independentes entre
si; `dataset` é barreira (junta tudo); `ml` lê só o dataset; `report` lê os CSVs
de achados. Scripts de apoio fora do `run_all.py`:
`collect_ck_ghidra.py`, `collect_native_resumable.py` (coletas
particionadas/retomáveis para o repo gigante `ghidra`).

---

## 5. Mapeamento script → fase

| Script | Fase | Saída |
|---|---|---|
| `clone_repositories.py` | clone | `repos/` |
| `collect_loc_metrics.py` | loc | `loc.csv` |
| `collect_complexity_metrics.py` | complexity | `complexity.csv` (lizard) |
| `collect_sonarqube_metrics.py` | sonarqube | `sonarqube.csv` |
| `collect_semgrep_metrics.py` | semgrep | `semgrep_findings.csv` |
| `collect_codeql_metrics.py` | codeql | `codeql_findings.csv` |
| `collect_pydriller_metrics.py` | pydriller | `pydriller_metrics.csv` |
| `collect_ck_metrics.py` | ck | `ck_metrics.csv` |
| `collect_osv_metrics.py` | osv | `osv_findings.csv`, `osv_summary.csv` |
| `collect_gitleaks_metrics.py` | secrets | `secrets_findings.csv`, `secrets_summary.csv` |
| `build_security_dataset.py` | dataset | `security_dataset.csv`, `dataset_dictionary.md` |
| `ml_security_pipeline.py` | ml | `ml_results.csv`, `ml_confusions.csv`, `charts/*.png` |
| `generate_comparative_report.py` | report | `comparative_report.md` |
| `common.py` | — | utilitários compartilhados |
| `setup_dev_tools.ps1` | setup | instala binários em `developer-tools/` |

---

## 6. Dataset e ML

**Unidade de análise:** arquivo `.java`. **31.622 arquivos**, **560 positivos**
(risco de segurança) ≈ **1,77%** → forte desbalanceamento de classes.

**Target:** `has_security_risk` (binário; 1 = Semgrep OR CodeQL).

**Features** (ver `data/dataset_dictionary.md`):
- **Estruturais (SonarQube):** `sonar_ncloc`, `sonar_complexity`,
  `sonar_cognitive_complexity`, `sonar_duplicated_lines_density`,
  `sonar_code_smells`, `sonar_sqale_index`, etc.
- **OO (CK):** `wmc`, `dit`, `noc`, `cbo`, `rfc`, `lcom`, `lcom_star`, `tcc`,
  `lcc`, `num_methods`, `num_fields`, `num_classes`.
  - Agregação classe→arquivo: WMC/RFC/num_methods por **soma**;
    DIT/NOC/CBO/LCOM/TCC por **máximo**.
- **Processo (PyDriller):** `commits`, `distinct_authors`, `lines_added`,
  `lines_removed`, `churn`, `file_age_days`, `days_since_change`.
- **Excluídas (anti-vazamento):** `n_semgrep`, `n_codeql`.

**Modelagem** (`ml_security_pipeline.py`):
- **Validação:** `GroupKFold` **por repositório** (grupos = repos) para evitar
  vazamento entre treino/teste do mesmo projeto.
- **Desbalanceamento:** SMOTE (`imbalanced-learn`).
- **Modelos:** LogisticRegression, DecisionTree, RandomForest, XGBoost, LightGBM.
- **Métricas:** priorizar **ROC-AUC / Recall / F1** (não accuracy, dado o
  desbalanceamento).
- **Interpretabilidade:** SHAP + importância de features (RandomForest).

**Resultados (médias GroupKFold — de `reports/comparative_report.md`):**

| model | precision | recall | f1 | roc_auc |
|---|---|---|---|---|
| LogisticRegression | 0.089 | 0.644 | 0.155 | 0.785 |
| DecisionTree | 0.098 | 0.408 | 0.150 | 0.719 |
| RandomForest | 0.385 | 0.166 | 0.195 | **0.859** |
| XGBoost | 0.319 | 0.136 | 0.168 | 0.820 |
| LightGBM | 0.341 | 0.121 | 0.155 | 0.837 |

Trade-off central: RandomForest tem o melhor ROC-AUC; LogisticRegression tem o
maior recall (útil quando falso-negativo é o pior erro).

---

## 7. Ambiente e ferramentas (versões — `TOOLS_VERSIONS.md`)

- **Python** 3.10+ (testado com 3.12.0); **JDK** OpenJDK 24 (para o CK);
  **Git** e **Docker** (servidor SonarQube) no PATH.
- **Python libs** (`requirements.txt`, versões `>=`): pandas, numpy, requests,
  lizard, pydriller, detect-secrets, scikit-learn, xgboost, lightgbm, shap,
  imbalanced-learn, matplotlib, seaborn, tabulate, python-dotenv.
  - **Atenção:** `semgrep` é usado mas **não está** no `requirements.txt`
    (`pip install semgrep` à parte).
- **Binários pesados** (em `developer-tools/`, gitignored; resolvidos por
  `common.find_external_tool`: env var → PATH → `developer-tools/`):
  CK 0.7.0, Gitleaks 8.30.1, SonarScanner CLI 6.2.1, CodeQL 2.25.6.
- **SonarQube server** (Community) roda via Docker na porta 9000.
- **OSV** é API HTTP (sem binário).

**Credenciais (`.env`, não versionado, lido por `common.py`):**
`GITHUB_TOKEN` (ou `GH_TOKEN`), `SONAR_HOST_URL` (padrão `http://localhost:9000`),
`SONAR_TOKEN` (precisa ser **User Token**, não Global Analysis Token).

**Não há Dockerfile/compose no projeto** — Docker só sobe o SonarQube.

---

## 8. Como executar (resumo)

```powershell
# 1. Ferramentas pesadas → developer-tools/
pwsh -File scripts/setup_dev_tools.ps1

# 2. Servidor SonarQube (gere um USER TOKEN em My Account > Security)
docker run -d --name sonarqube -p 9000:9000 sonarqube:community

# 3. Ambiente Python
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install semgrep            # não está no requirements.txt

# 4. Credenciais
Copy-Item .env.example .env    # editar GITHUB_TOKEN, SONAR_HOST_URL, SONAR_TOKEN

# 5. Pipeline inteiro
python scripts/run_all.py
#   pular fases:      python scripts/run_all.py --skip clone
#   só algumas fases: python scripts/run_all.py --only sonarqube,codeql,dataset,ml
#   só ML:            python scripts/run_all.py --only ml   (requer security_dataset.csv)
```

Os scripts resolvem caminhos de forma absoluta em `common.py` → funcionam de
qualquer diretório, mas assumem a raiz `github-metrics-analyzer/`.

---

## 9. Artigo científico (`Artigo/`)

- Padrão **SBC** (6–10 páginas), pronto para Overleaf (pdfLaTeX).
- `main.tex` já contém os números reais do estudo; estrutura obrigatória:
  Introdução → Fundamentação → Metodologia → Resultados → Conclusão → Referências.
- Números vêm de `reports/comparative_report.md`, `reports/ml_results.csv` e
  `data/security_dataset.csv`.
- Compilar local: `pdflatex main && bibtex main && pdflatex main && pdflatex main`.
- **Referências** (`referencias.bib`) são obras reais (ISO 25000/25010/25023,
  McCabe 1976, Chidamber & Kemerer 1994, PyDriller/Spadini 2018, SMOTE/Chawla
  2002, Random Forest/Breiman 2001, XGBoost 2016, LightGBM 2017, SHAP 2017) —
  conferir autores/ano/DOI antes de submeter.

---

## 10. Convenções e decisões de projeto (para agentes)

- **Idempotência:** reexecutar qualquer fase regrava CSVs sem duplicar; clones
  existentes são atualizados via `git fetch`, não reclonados.
- **Robustez:** exceções capturadas por repo/arquivo; falhas logadas sem abortar.
- **Encoding:** saídas de subprocesso em `utf-8` com `errors="ignore"`.
- **Rate limit:** `common.github_get` respeita `Retry-After` e
  `X-RateLimit-Reset`, paginação `per_page=100`.
- **Sem build/compilação** — respeitar sempre esse princípio ao mexer em coletas.
- **Segurança:** nunca commitar tokens; `.env` está no `.gitignore`; escopo
  mínimo `public_repo`.
- **Limitação de validade externa:** 4 dos 10 repos pertencem ao ecossistema
  **DataWave** (variável de confusão) — mencionado nas limitações do artigo.
- **Métrica não coletável** aparece como ausente/zero, **nunca estimada**.

---

## 11. Onde procurar mais detalhes

| Preciso de… | Arquivo |
|---|---|
| Enunciado/requisitos do trabalho | `AP2_Trabalho_Final.md` |
| Documentação de uso do pipeline | `github-metrics-analyzer/README.md` |
| Resumo técnico profundo (versões, decisões) | `github-metrics-analyzer/resumo.md` |
| Versões exatas das ferramentas | `github-metrics-analyzer/TOOLS_VERSIONS.md` |
| Dicionário de colunas do dataset | `github-metrics-analyzer/data/dataset_dictionary.md` |
| Resultados comparativos + ML | `github-metrics-analyzer/reports/comparative_report.md` |
| Artigo científico | `Artigo/main.tex`, `Artigo/README.md` |
```