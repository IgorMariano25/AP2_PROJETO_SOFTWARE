# GitHub Metrics Analyzer — AP2 Security Analysis Pipeline

Pipeline **estática, automatizada e reprodutível** para estudo empírico de
**postura de segurança** em repositórios Java da organização
`NationalSecurityAgency` no GitHub, fundamentado em **ISO/IEC 25010/25023**
e com predição por **Machine Learning**.

> **Princípio central:** análise exclusivamente estática, sobre código-fonte
> clonado. **Nenhum projeto é compilado, buildado ou executado.**

## Fontes de dados (AP2 — estudo de segurança)

| Dimensão | Ferramenta | ISO 25010 (25023) |
|---|---|---|
| **SAST — alvo do ML** | **Semgrep ∪ CodeQL** (união) | Segurança (Integridade, Confidencialidade, Autenticidade) |
| **Estrutura/complexidade** | **SonarQube** (canônico) · lizard (fallback) | Manutenibilidade / Confiabilidade |
| **Métricas OO** | CK JAR (Maurício Aniche) | Manutenibilidade |
| **Métricas de processo** | PyDriller | Manutenibilidade |
| **SCA (dependências)** | OSV API (Python, sem binário) | Segurança > Resistência |
| **Segredos expostos** | **Gitleaks + detect-secrets** (união deduplicada) | Segurança > Confidencialidade |
| **Linhas de código** | cloc (fallback Python) | — (normalização) |

> **Alvo (união Semgrep ∪ CodeQL):** um arquivo é positivo se **qualquer** das
> duas SASTs o sinaliza (maximiza recall — em segurança, falso-negativo é o pior
> erro, §8.4). As contagens por ferramenta (`n_semgrep`, `n_codeql`) entram no
> dataset apenas para análise de concordância e são **excluídas das features**
> do ML (anti-vazamento).
>
> **Estrutura (SonarQube canônico):** quando `data/sonarqube.csv` existe, ele é a
> fonte de complexidade/duplicação/code smells/comentários; o lizard só é usado
> como fallback offline — **nunca os dois juntos** (regra "uma fonte por
> dimensão", evita multicolinearidade). SonarQube **não** é oráculo de segurança
> (sem bytecode, §9.1): suas medidas de segurança são ignoradas.
>
> **Segredos (descritivo):** Gitleaks (canônico) + detect-secrets, com **dedup
> por (arquivo, linha, tipo)** e coluna `detected_by` para validação cruzada.
> Não é feature/alvo do ML, então combinar não causa vazamento.

---

## Fonte única por dimensão OO (CK)

As métricas orientadas a objetos vêm **exclusivamente do CK** (Maurício Aniche),
a ferramenta canônica do estudo (WMC, DIT, NOC, CBO, RFC, LCOM …). Mantemos
**uma única fonte por dimensão** (regra metodológica do estudo): não somamos um
segundo parser estrutural ao CK, pois colunas duplicadas introduzem
multicolinearidade e contaminam o *ranking de importância de features* — o
resultado central que liga as métricas às sub-características da ISO 25010. A
complexidade ciclomática fica a cargo do `lizard` (Python, analisa Java
nativamente), dimensão distinta da estrutura OO.

---

## Estrutura

```
github-metrics-analyzer/
├── repos.txt                 # lista owner/repo (gerada pela Fase 1)
├── repos/                    # clones (gerado)
├── data/                     # CSVs de saída
├── metrics.db                # SQLite consolidado (opcional)
├── reports/
│   ├── report.md
│   └── charts/*.png
├── scripts/                  # uma fase por arquivo + common.py + run_all.py
├── requirements.txt
└── README.md
```

---

## Setup

### 1. Ferramentas externas (Fase 0)

```powershell
# GitHub CLI (opcional, recomendado)
winget install GitHub.cli        # Windows
gh auth login

# cloc (opcional; há fallback em Python)
winget install AlDanial.Cloc     # Windows

# Git e JDK 17+ devem estar no PATH (JDK necessário para o CK)
```

#### Ferramentas pesadas (CK, SonarScanner, CodeQL, Gitleaks)

Binários pesados **não versionados** no Git (gitignorados), instalados na pasta
`developer-tools/<ferramenta>` dentro do projeto (uma por subpasta). Os coletores
os resolvem automaticamente (env → `PATH` → `developer-tools/`), sem mexer no
`PATH` global. **Se uma ferramenta faltar, a fase grava saída vazia e o pipeline
degrada com elegância** (lizard no lugar do SonarQube; alvo só com Semgrep; só
detect-secrets). Para outro destino, defina `$env:DEVELOPER_TOOLS`.

**Forma recomendada — instalador idempotente** (migra o CK e baixa o resto):

```powershell
pwsh -File scripts/setup_dev_tools.ps1                  # CK, gitleaks, sonar-scanner, codeql
pwsh -File scripts/setup_dev_tools.ps1 -PullSonarQubeImage   # + imagem Docker do servidor
# -DevTools D:\tools  → outro destino   |   -SkipCodeQL  → pula o bundle (~1 GB)
```

Para outro destino, defina `$env:DEVELOPER_TOOLS` (lido por `common.py`) ou
aponte caminhos explícitos no `.env` (`CODEQL_CLI`, `SONARSCANNER_CLI`,
`GITLEAKS_CLI`, `DEVELOPER_TOOLS`).

**Servidor SonarQube** (métricas estruturais) roda via Docker — não fica em pasta:

```powershell
docker run -d --name sonarqube -p 9000:9000 sonarqube:community
#   http://localhost:9000 (admin/admin) → troque a senha, gere um token e
#   preencha SONAR_HOST_URL / SONAR_TOKEN no .env
```

> **Princípio sem build:** o SonarScanner roda em modo source-only
> (`sonar.java.binaries` apontado para os próprios fontes); regras que exigem
> bytecode simplesmente não disparam — usamos só as métricas estruturais (AST).
> O CodeQL extrai Java em `--build-mode=none` (sem compilar).

### 2. Ambiente Python

```powershell
cd github-metrics-analyzer
python -m venv .venv
.\.venv\Scripts\Activate.ps1      # Windows
# source .venv/bin/activate       # Linux/macOS
pip install -r requirements.txt
```

### 3. Token do GitHub

Sem token o limite é ~60 req/h; com token pessoal ~5.000 req/h.

**Forma recomendada (arquivo `.env`, não versionado):**

```powershell
Copy-Item .env.example .env      # depois edite .env e cole o seu token
```

O `.env` é carregado automaticamente por `scripts/common.py` (via
`python-dotenv`, com fallback manual) e está listado no `.gitignore`, então
**nunca** é commitado.

**Alternativa (variável de ambiente da sessão):**

```powershell
$env:GITHUB_TOKEN = "ghp_xxxxxxxxxxxx"   # Windows PowerShell
# export GITHUB_TOKEN=ghp_xxxxxxxxxxxx   # Linux/macOS
```

O código lê `GITHUB_TOKEN` (ou `GH_TOKEN`) e trata `403/429` com backoff.

> **Segurança:** nunca escreva o token no código; use só `public_repo` como
> escopo e defina expiração curta. Se o token vazar, revogue-o imediatamente em
> https://github.com/settings/tokens.

---

## Execução

Rodar a pipeline inteira:

```powershell
python scripts/run_all.py
```

Pular fases (ex.: repositórios já clonados):

```powershell
python scripts/run_all.py --skip search,clone
```

Rodar apenas algumas fases:

```powershell
python scripts/run_all.py --only loc,complexity,semgrep,ck,dataset,ml,report
```

Ou rodar cada fase individualmente:

```powershell
python scripts/clone_repositories.py            # clone (sem build)
python scripts/collect_loc_metrics.py           # LOC (normalização)
python scripts/collect_complexity_metrics.py    # lizard (fallback estrutural)
python scripts/collect_sonarqube_metrics.py     # SonarQube (estrutural canônico)
python scripts/collect_semgrep_metrics.py       # SAST #1 → target do ML
python scripts/collect_codeql_metrics.py        # SAST #2 → target (união)
python scripts/collect_pydriller_metrics.py     # processo (feature)
python scripts/collect_ck_metrics.py            # CK / OO (feature)
python scripts/collect_osv_metrics.py           # SCA (descritivo)
python scripts/collect_gitleaks_metrics.py      # segredos: Gitleaks + detect-secrets
python scripts/build_security_dataset.py        # → security_dataset.csv
python scripts/ml_security_pipeline.py          # ML: GroupKFold, modelos, ROC, SHAP
```

> `search_repositories.py` (seleção dos repos) e `collect_ck_ghidra.py` /
> `collect_native_resumable.py` (coletas particionadas/retomáveis) são scripts
> de apoio, executados sob demanda — não fazem parte do fluxo padrão.

> Os scripts assumem que são executados a partir da raiz do projeto
> (`github-metrics-analyzer/`). Os caminhos são resolvidos de forma absoluta
> em `scripts/common.py`, então também funcionam de qualquer diretório.

---

## Saídas

| Arquivo | Conteúdo | Papel no estudo |
|---|---|---|
| `data/repositories.csv` | metadados do GitHub (stars, licença, …) | descritivo da seleção |
| `data/loc.csv` | LOC (total e Java) por repo | normalização por KLOC |
| `data/complexity.csv` | NLOC, CCN, tokens, parâmetros por método | feature estrutural (lizard, fallback) |
| `data/sonarqube.csv` | complexity, cognitive, duplicação, code smells, comentários | feature estrutural (SonarQube, canônico) |
| `data/codeql_findings.csv` | achados de segurança por arquivo (CWE) | **alvo do ML** (união com Semgrep) |
| `data/ck_metrics.csv` | WMC, DIT, CBO, RFC, LCOM … por arquivo | feature (CK) |
| `data/pydriller_metrics.csv` | commits, autores, churn, idade por arquivo | feature (processo) |
| `data/semgrep_findings.csv` | achados de segurança por arquivo (CWE) | **alvo do ML** |
| `data/osv_*.csv` | CVEs declarados (pom.xml/Gradle) | descritivo (SCA) |
| `data/secrets_*.csv` | segredos detectados | descritivo (Confidencialidade) |
| `data/security_dataset.csv` | dataset nível-arquivo (features + target) | entrada do ML |
| `data/dataset_dictionary.md` | dicionário de colunas + mapeamento ISO 25010 | documentação |
| `reports/charts/*.png` | ROC, importância de features, SHAP, matriz de confusão | resultados do ML |

---

## Decisões de projeto

- **Idempotência:** reexecutar qualquer fase regrava os CSVs sem duplicar; clones
  existentes são atualizados via `git fetch` em vez de reclonados.
- **Robustez:** exceções são capturadas por repositório/arquivo sem abortar a
  pipeline; falhas são logadas.
- **Encoding:** todas as saídas de subprocesso usam `utf-8` com `errors="ignore"`.
- **Rate limit:** `common.github_get` respeita `Retry-After` e
  `X-RateLimit-Reset`, com paginação `per_page=100`.
- **Fallbacks:** sem `cloc`, usa contador de linhas em Python; sem `gh`, usa a
  REST API; busca tem lista curada de fallback.
