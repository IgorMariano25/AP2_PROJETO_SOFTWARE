# GitHub Metrics Analyzer (MSR Pipeline)

Pipeline **completa, automatizada e reprodutível** de Mineração de Repositórios
de Software (MSR) para repositórios **Java** grandes e ativos do GitHub.

O princípio central é: **cada métrica vem da melhor fonte**.

| Tipo de dado | Fonte usada |
|---|---|
| Buscar repositórios | GitHub Search API / `gh` CLI |
| Stars, forks, linguagem, licença, `pushed_at` | GitHub REST API |
| Total de commits / histórico | Git local (`git rev-list`, `git log`) |
| Commits por desenvolvedor | `git shortlog -sne --all` |
| Commits por arquivo + churn | `git log --numstat` |
| Pull requests + commits por PR | GitHub REST API |
| Linhas de código | `cloc` (fallback: contador Python) |
| Classes/interfaces/herança | `javalang` (parser Java em Python) |
| Complexidade ciclomática | `lizard` |
| Métricas de teste | varredura de `src/test`, `@Test`, frameworks |

---

## Por que `javalang` e não JavaParser?

O **JavaParser é uma biblioteca Java**, exigiria um utilitário Java empacotado
com Maven/Gradle e chamado via `subprocess` (opção A do enunciado). Para manter
**toda a pipeline em uma única linguagem (Python)** e evitar dependência de JVM
e build externo, escolhemos a **opção B** com **`javalang`** — um parser Java
puro em Python. É mais simples de integrar e suficiente para extrair classes,
interfaces, classes abstratas, métodos, atributos, `extends` e `implements`.
A complexidade ciclomática fica a cargo do `lizard`, que também é Python e
analisa Java nativamente.

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
# sudo apt install gh            # Linux
gh auth login

# cloc (opcional; há fallback em Python)
winget install AlDanial.Cloc     # Windows
# sudo apt install cloc          # Linux  /  npm install -g cloc

# Git deve estar instalado e no PATH
```

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
python scripts/run_all.py --only loc,complexity,structure,indicators,report
```

Ou rodar cada fase individualmente:

```powershell
python scripts/search_repositories.py
python scripts/clone_repositories.py
python scripts/collect_git_metrics.py
python scripts/collect_pr_metrics.py
python scripts/collect_loc_metrics.py
python scripts/collect_complexity_metrics.py
python scripts/collect_structure_metrics.py
python scripts/collect_test_metrics.py
python scripts/consolidate.py
python scripts/compute_indicators.py
python scripts/generate_report.py
```

> Os scripts assumem que são executados a partir da raiz do projeto
> (`github-metrics-analyzer/`). Os caminhos são resolvidos de forma absoluta
> em `scripts/common.py`, então também funcionam de qualquer diretório.

---

## Saídas

| Arquivo | Conteúdo |
|---|---|
| `data/repositories.csv` | metadados do GitHub |
| `data/commits.csv` | resumo de commits por repo |
| `data/developers.csv` | commits por desenvolvedor |
| `data/files.csv` | commits + churn por arquivo |
| `data/pull_requests.csv` | PRs com estado, datas, commits |
| `data/loc.csv` | LOC (total e Java) |
| `data/structure.csv` | classes/interfaces/herança/métodos |
| `data/complexity.csv` | NLOC, CCN, tokens, parâmetros por método |
| `data/tests.csv` | testes, `@Test`, ratio main/test, frameworks |
| `data/quality_indicators.csv` | indicadores derivados por repo |
| `data/hotspots.csv` | hotspots (commits × complexidade) |
| `metrics.db` | SQLite com uma tabela por CSV |
| `reports/report.md` | relatório final + gráficos |

---

## Indicadores derivados

- **Atividade do projeto:** commits + dias ativos + PRs.
- **Distribuição de contribuição:** % de commits dos top 5 contribuidores.
- **Risco de concentração:** classificação low/medium/high.
- **Complexidade média:** média de CCN por método.
- **Testabilidade:** nº de testes / nº de métodos.
- **Manutenibilidade:** LOC, CCN e tamanho médio dos métodos.
- **Modularidade:** classes, interfaces e heranças.
- **Saúde de PRs:** abertas vs fechadas, commits por PR, tempo médio de fechamento.
- **Hotspots:** `commits no arquivo × CCN médio do arquivo` — candidatos a refatoração.

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
