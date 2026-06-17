# Resumo Técnico do Projeto — *GitHub Metrics Analyzer* (AP2)

> Documento gerado a partir da leitura dos arquivos reais do repositório
> (`scripts/`, `requirements.txt`, `setup_dev_tools.ps1`, `TOOLS_VERSIONS.md` e
> os cabeçalhos dos CSVs em `data/`). Afirmações não óbvias citam o arquivo de
> origem. Itens que **não** puderam ser determinados a partir do código estão
> marcados com **⚠️ não determinado pelo código**.

---

## 1. Visão geral

Pipeline **estática, automatizada e reprodutível** de Mineração de Repositórios
de Software (MSR) que coleta métricas de qualidade e de segurança de 10
repositórios Java da organização `NationalSecurityAgency` no GitHub, monta um
*dataset* em nível de arquivo e treina modelos de *Machine Learning* para
**prever quais arquivos `.java` são propensos a risco de segurança**, ancorando
as métricas na norma ISO/IEC 25010. O princípio central, declarado em todos os
coletores, é **analisar apenas o código-fonte clonado: nenhum projeto é
compilado, *buildado* ou executado** (ver docstrings de
`collect_semgrep_metrics.py`, `collect_codeql_metrics.py` e
`collect_sonarqube_metrics.py`).

---

## 2. Dependências e pré-requisitos

### 2.1 Runtime / ambiente

| Componente | Versão | Origem da informação |
|---|---|---|
| Python | 3.10+ (testado com **3.12.0**) | `from __future__ import annotations` + anotações `dict \| None`/`list[dict]`; versão usada em `TOOLS_VERSIONS.md` |
| Git | presente no `PATH` | `clone_repositories.py` chama `git fetch`/`git clone` |
| JDK (para o CK) | **OpenJDK 24.0.2** (usado) | CK roda via `java -jar ck.jar` (`collect_ck_metrics.py`); versão em `TOOLS_VERSIONS.md` |
| Docker | necessário p/ o servidor SonarQube | `README.md` (`docker run ... sonarqube:community`) |

### 2.2 Dependências Python (`requirements.txt`)

Versões declaradas como **mínimos** (`>=`). As versões efetivamente usadas estão
fixadas em `TOOLS_VERSIONS.md`.

| Pacote | Mínimo (`requirements.txt`) | Papel |
|---|---|---|
| pandas | >=2.0.0 | montagem do dataset |
| requests | >=2.31.0 | GitHub API / OSV / SonarQube Web API |
| numpy | >=1.24.0 | numérico |
| lizard | >=1.17.10 | complexidade ciclomática por método |
| pydriller | >=2.6 | métricas de processo (git) |
| detect-secrets | >=1.4.0 | detecção de segredos (Python) |
| scikit-learn | >=1.3.0 | ML (modelos, GroupKFold, métricas) |
| xgboost | >=2.0.0 | ML (modelo) |
| lightgbm | >=4.0.0 | ML (modelo) |
| shap | >=0.44.0 | interpretabilidade |
| imbalanced-learn | >=0.11.0 | SMOTE (desbalanceamento) |
| matplotlib | >=3.7.0 | gráficos |
| seaborn | >=0.12.0 | gráficos |
| tabulate | >=0.9.0 | tabelas no relatório |
| python-dotenv | >=1.0.0 | carregar `.env` (há *fallback* manual em `common.py`) |

> **⚠️ Atenção (semgrep):** `collect_semgrep_metrics.py` invoca o executável
> `semgrep` (do venv, ou do `PATH`), mas **o semgrep NÃO consta no
> `requirements.txt`**. Precisa ser instalado à parte (`pip install semgrep`).
> Versão usada: 1.165.0 (`TOOLS_VERSIONS.md`).

### 2.3 Ferramentas externas pesadas (fora do Git)

Resolvidas por `common.find_external_tool` na ordem **env var → `PATH` →
`developer-tools/<ferramenta>`** (pasta dentro do projeto, *gitignored*).
Instaladas pelo script idempotente `scripts/setup_dev_tools.ps1`; versões
fixadas nele e em `TOOLS_VERSIONS.md`.

| Ferramenta | Versão | Como é resolvida |
|---|---|---|
| CK (Maurício Aniche) | 0.7.0 | `developer-tools/ck/ck.jar` (`collect_ck_metrics.py`) |
| Gitleaks | 8.30.1 | `developer-tools/gitleaks/gitleaks.exe` (`collect_gitleaks_metrics.py`) |
| SonarScanner CLI | 6.2.1.4610 | `developer-tools/sonar-scanner/bin/sonar-scanner.bat` (`collect_sonarqube_metrics.py`) |
| CodeQL (bundle CLI + packs) | 2.25.6 | `developer-tools/codeql/codeql.exe` (`collect_codeql_metrics.py`) |
| SonarQube (servidor) | 26.6.0.123539 (Community) | imagem Docker `sonarqube:community` (não fica em pasta) |
| OSV | API `https://api.osv.dev/v1/query` | sem binário; consultada via `requests` |
| cloc | opcional | `collect_loc_metrics.py` usa cloc se disponível, com *fallback* em Python |

> **Degradação graciosa:** se uma ferramenta pesada faltar, a fase grava saída
> vazia e o pipeline continua (lizard no lugar do SonarQube; alvo só com
> Semgrep; só detect-secrets). Ver tratamento em cada coletor.

### 2.4 Credenciais (`.env`)

Lido por `common.py` (via `python-dotenv`, com *fallback* manual).

| Variável | Uso |
|---|---|
| `GITHUB_TOKEN` (ou `GH_TOKEN`) | GitHub API com *rate limit* maior (`common.github_get`) |
| `SONAR_HOST_URL` | URL do servidor SonarQube (padrão `http://localhost:9000`) |
| `SONAR_TOKEN` | **User Token** do SonarQube (Global Analysis Token retorna 403 na leitura de métricas) |
| `DEVELOPER_TOOLS`, `*_CLI` | (opcionais) sobrepõem caminhos de ferramentas |

---

## 3. Como rodar

```powershell
# 1. Ferramentas pesadas (CK, Gitleaks, SonarScanner, CodeQL) → developer-tools/
pwsh -File scripts/setup_dev_tools.ps1
#    + imagem Docker do servidor SonarQube:
pwsh -File scripts/setup_dev_tools.ps1 -PullSonarQubeImage

# 2. Servidor SonarQube (Docker) — gere um USER TOKEN em My Account > Security
docker run -d --name sonarqube -p 9000:9000 sonarqube:community

# 3. Ambiente Python
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install semgrep            # não está no requirements.txt

# 4. Credenciais
Copy-Item .env.example .env    # edite e preencha GITHUB_TOKEN, SONAR_HOST_URL, SONAR_TOKEN

# 5. Executar o pipeline inteiro
python scripts/run_all.py
#    repos já clonados:        python scripts/run_all.py --skip clone
#    apenas algumas fases:     python scripts/run_all.py --only sonarqube,codeql,dataset,ml

# 6. Rodar SOMENTE o Machine Learning (dataset já gerado)
python scripts/run_all.py --only ml
#    ou, diretamente o módulo:
python scripts/ml_security_pipeline.py
#    (pré-requisito: data/security_dataset.csv já existe;
#     se não, gere antes com:  python scripts/run_all.py --only dataset)
```

Fonte: `README.md`, `setup_dev_tools.ps1`, `run_all.py`, `ml_security_pipeline.py`.

---

## 4. Fluxo de execução

`scripts/run_all.py` define a ordem canônica das fases (lista `PHASES`). Cada
fase é um módulo independente importado e executado por `module.main()`; falhas
em uma fase são logadas e **não** abortam o restante (a menos que `--strict`).
Todos os coletores compartilham `common.py` (caminhos, logging, `.env`,
resolução de ferramentas, GitHub API).

```
clone ─────────► repos/ (clones git, sem build)
   │
   ├─► loc ───────────► data/loc.csv            (normalização KLOC)
   ├─► complexity ────► data/complexity.csv     (lizard; FALLBACK estrutural)
   ├─► sonarqube ─────► data/sonarqube.csv      (estrutural CANÔNICO)
   ├─► semgrep ───────► data/semgrep_findings.csv  ┐ alvo do ML
   ├─► codeql ────────► data/codeql_findings.csv   ┘ (união)
   ├─► pydriller ─────► data/pydriller_metrics.csv (processo, feature)
   ├─► ck ────────────► data/ck_metrics.csv        (OO, feature)
   ├─► osv ───────────► data/osv_findings.csv + osv_summary.csv (descritivo)
   └─► secrets ───────► data/secrets_findings.csv + secrets_summary.csv (descritivo)
                                   │
   dataset ◄────────────────────── (lê TODOS os CSVs acima)
       └─► data/security_dataset.csv  +  data/dataset_dictionary.md
                                   │
   ml ◄──────────────────────────── (lê security_dataset.csv)
       └─► reports/ml_results.csv, ml_confusions.csv, charts/*.png
                                   │
   report ◄──────────────────────── (lê os CSVs de achados/posturas)
       └─► reports/comparative_report.md + charts/*.png
```

**Como um alimenta o outro (dependências reais):**

1. **`clone`** precisa rodar primeiro — cria `repos/`, que todos os coletores
   iteram via `common.iter_repo_dirs()`.
2. As 9 fases de coleta (`loc`…`secrets`) são **independentes entre si** — só
   dependem dos clones. Podem rodar em qualquer ordem.
3. **`dataset`** (`build_security_dataset.py`) é uma **barreira**: junta todos
   os CSVs de coleta em `security_dataset.csv`.
4. **`ml`** (`ml_security_pipeline.py`) lê **apenas** `security_dataset.csv`.
5. **`report`** lê os CSVs de achados/posturas (Semgrep, OSV, segredos) para a
   descrição comparativa.

> **Scripts de apoio (fora do `run_all.py`):** `collect_ck_ghidra.py` e
> `collect_native_resumable.py` são variantes particionadas/retomáveis das
> coletas de CK e LOC; `search_repositories.py` gera `data/repositories.csv` —
> **⚠️ a fonte `.py` não está mais no repositório (só o `.pyc` em
> `__pycache__/`)**, então esse arquivo é executado sob demanda e não faz parte
> do fluxo padrão.

---

## 5. Docker

**⚠️ Não há `Dockerfile` nem `docker-compose.yml` no projeto.** A varredura por
`Dockerfile*`/`docker-compose*`/`*.yml` não retornou nada (fora de `.venv/` e
`developer-tools/`). Portanto, **nada do pipeline em si é containerizado**.

O Docker é usado **apenas para subir o servidor SonarQube**, via comando avulso
documentado no `README.md` e suportado por `setup_dev_tools.ps1`
(`-PullSonarQubeImage`):

```powershell
docker run -d --name sonarqube -p 9000:9000 sonarqube:community
```

- **Serviço que sobe:** um único container `sonarqube:community`, expondo a
  porta **9000** (Web UI + Web API).
- **Como interage com o pipeline:** `collect_sonarqube_metrics.py` (1) roda o
  **SonarScanner** (binário local em `developer-tools/`) apontando para
  `SONAR_HOST_URL`, e (2) lê as métricas de volta pela **Web API**
  (`/api/ce/component` para aguardar a análise e
  `/api/measures/component_tree?qualifiers=FIL` para as medidas por arquivo),
  autenticando com `SONAR_TOKEN`.
- O scanner roda em modo *source-only* (sem `sonar-project.properties`; as
  propriedades são passadas por linha de comando, ver Seção 6).

---

## 6. Ferramentas de análise

| Ferramenta | Papel no estudo | Como se integra | Decisão |
|---|---|---|---|
| **Semgrep** (`--config auto`) | SAST — metade do **alvo** do ML | `collect_semgrep_metrics.py` roda o binário sobre os `.java`; achados → `semgrep_findings.csv` | Escolhida (alvo) |
| **CodeQL** (`--build-mode=none`, suíte `java-security-extended`) | SAST — outra metade do **alvo** (união) | `collect_codeql_metrics.py` cria DB sem compilar, analisa, parseia SARIF → `codeql_findings.csv` | Escolhida (alvo) |
| **SonarQube** (servidor + SonarScanner) | Métricas **estruturais** (complexidade, duplicação, *code smells*, dívida técnica) | scanner *source-only* + Web API → `sonarqube.csv` | **Canônico** p/ estrutura |
| **lizard** | Complexidade ciclomática por método | `collect_complexity_metrics.py` (API Python) → `complexity.csv` | *Fallback* estrutural (offline) |
| **CK** (Maurício Aniche) | Métricas OO (WMC, DIT, CBO, RFC, LCOM…) | `java -jar ck.jar`, agregado a nível de arquivo → `ck_metrics.csv` | Escolhida (feature OO) |
| **PyDriller** | Métricas de processo (commits, autores, churn, idade) | percorre o histórico git → `pydriller_metrics.csv` | Escolhida (feature processo) |
| **OSV** (API) | SCA — CVEs em dependências declaradas | parseia `pom.xml`/Gradle e consulta a API → `osv_*.csv` | Escolhida (descritivo) |
| **Gitleaks** + **detect-secrets** | Detecção de segredos (união deduplicada) | dois scanners; dedup por (arquivo, linha, tipo) + coluna `detected_by` → `secrets_*.csv` | Escolhidas (descritivo) |
| **cloc** | Contagem de linhas (LOC) | usado se presente; senão *fallback* Python | Opcional |

**Por que SonarQube é só estrutural?** Sem *bytecode* (estudo 100% estático),
suas regras de segurança/bug que dependem de compilação **não disparam**; por
isso ele entra como fonte de **estrutura/manutenibilidade**, e o alvo de
segurança vem de Semgrep ∪ CodeQL. Configuração real do scanner
(`collect_sonarqube_metrics.py`, `_run_scanner`):

```
-Dsonar.sources=<repo>  -Dsonar.java.binaries=<repo>   (aponta p/ os próprios fontes)
-Dsonar.exclusions=**/*.jar,**/.git/**  -Dsonar.scm.disabled=true  -Dsonar.sourceEncoding=UTF-8
```

**Regra "uma fonte por dimensão":** SonarQube **ou** lizard para estrutura
(nunca os dois) — `build_security_dataset.structural_features()` usa SonarQube
quando `sonarqube.csv` existe e tem dados; senão cai no lizard.

---

## 7. Métricas

### 7.1 Linhas de código — `loc.csv` (`collect_loc_metrics.py`)

| Métrica | O que mede | Para que serve |
|---|---|---|
| `files` / `java_files` | nº total de arquivos / arquivos `.java` | dimensionar o repositório |
| `code` / `java_code` | linhas de código (total / Java) | normalização por **KLOC** |
| `comment` / `java_comment` | linhas de comentário | densidade de documentação |
| `blank` / `java_blank` | linhas em branco | — |

### 7.2 Complexidade por método — `complexity.csv` (lizard)

| Métrica | O que mede | Para que serve / interpretar |
|---|---|---|
| `nloc` | linhas de código do método (sem comentários) | tamanho do método |
| `ccn` | complexidade ciclomática (caminhos independentes) | quanto maior, mais difícil de testar |
| `tokens` | nº de tokens léxicos | proxy de tamanho/complexidade |
| `parameters` | nº de parâmetros | acoplamento de interface; alto = *code smell* |
| `length` | linhas totais (com comentários/branco) | tamanho bruto |

### 7.3 Estrutura/Manutenibilidade — `sonarqube.csv` (SonarQube Web API)

| Métrica | O que mede | Para que serve / interpretar |
|---|---|---|
| `ncloc` | linhas de código (sem comentário) | tamanho |
| `lines` | linhas físicas totais | tamanho bruto |
| `functions` / `classes` / `statements` | nº de funções / classes / *statements* | granularidade do arquivo |
| `complexity` | complexidade ciclomática | quanto maior, mais caminhos |
| `cognitive_complexity` | complexidade **cognitiva** (dificuldade de entendimento) | melhor proxy de legibilidade que a ciclomática |
| `duplicated_lines` / `_density` / `duplicated_blocks` | linhas/blocos duplicados e % | duplicação = dívida de manutenção |
| `comment_lines` / `_density` | comentários e % | documentação |
| `code_smells` | nº de *code smells* (problemas de manutenibilidade) | quanto maior, pior a manutenibilidade |
| `sqale_index` | **dívida técnica** (esforço de remediação, em min) | tempo estimado para "limpar" o arquivo |
| `sqale_debt_ratio` | razão custo-remediação / custo-desenvolvimento | % de dívida |
| `violations` | total de violações de regra | qualidade geral |
| `blocker/critical/major/minor_violations` | violações por severidade | priorização |

### 7.4 Métricas OO — `ck_metrics.csv` (CK, agregado a arquivo)

> Agregação classe→arquivo (`collect_ck_metrics.py`): WMC/RFC/num_methods por
> **soma**; DIT/NOC/CBO/LCOM/TCC por **máximo** (a classe mais "arriscada" domina).

| Métrica | O que mede | Para que serve / interpretar |
|---|---|---|
| `wmc` | *Weighted Methods per Class* (soma das complexidades dos métodos) | alto = classe complexa |
| `dit` | profundidade na árvore de herança | alto = mais herança, mais difícil de entender |
| `noc` | nº de subclasses | alto = mais impacto de mudança |
| `cbo` | acoplamento entre objetos | alto = mais dependências, pior manutenibilidade |
| `rfc` | *Response For a Class* (métodos próprios + chamados) | alto = interface/comportamento complexo |
| `lcom` / `lcom_star` | falta de coesão dos métodos | **alto = pior** (métodos pouco relacionados) |
| `tcc` / `lcc` | coesão *tight*/*loose* da classe | **alto = melhor** (mais coesa) |
| `num_methods` / `num_static_methods` | nº de métodos (total/estáticos) | tamanho da classe |
| `num_fields` / `num_static_fields` | nº de campos (total/estáticos) | estado da classe |
| `num_classes` | nº de classes no arquivo | múltiplas classes por arquivo |

### 7.5 Processo — `pydriller_metrics.csv` (PyDriller)

| Métrica | O que mede | Para que serve / interpretar |
|---|---|---|
| `commits` | nº de commits que tocaram o arquivo | atividade/instabilidade |
| `distinct_authors` | nº de desenvolvedores distintos | "muitas mãos" = mais risco |
| `lines_added` / `lines_removed` | linhas adicionadas/removidas no histórico | volume de mudança |
| `churn` | `lines_added + lines_removed` | rotatividade de código |
| `file_age_days` | dias entre 1º e último commit do arquivo | maturidade |
| `days_since_change` | dias desde a última alteração | recência da mudança |

### 7.6 Achados de segurança — `semgrep_findings.csv` / `codeql_findings.csv`

| Coluna | O que mede |
|---|---|
| `rule_id` | regra que disparou |
| `severity` | severidade reportada pela ferramenta |
| `cwe` | CWE(s) associada(s) (mapeável à ISO/IEC 25010) |
| `message` | descrição do achado |

### 7.7 SCA — `osv_findings.csv` / `osv_summary.csv` (OSV)

| Coluna | O que mede |
|---|---|
| `package_name` / `version` | dependência declarada e versão |
| `vuln_id` | identificador da vulnerabilidade (CVE/GHSA) |
| `severity_score` / `severity_label` | score CVSS e rótulo |
| `title` | título da vulnerabilidade |
| `deps_declared` / `deps_queryable` | dependências encontradas / consultáveis |
| `vulns_direct` + `vulns_critical/high/medium/low` | CVEs em dependências **diretas**, por severidade |
| `avg_cvss` | CVSS médio |

> **Limitação (declarada no código):** só dependências **diretas** dos
> manifestos; transitivas exigiriam *build*.

### 7.8 Segredos — `secrets_findings.csv` / `secrets_summary.csv`

| Coluna | O que mede |
|---|---|
| `secret_type` | tipo de segredo detectado |
| `line_number` | linha do achado |
| `detected_by` | `gitleaks` / `detect-secrets` / `both` (validação cruzada) |
| `by_gitleaks` / `by_detect_secrets` / `by_both` | contagens por ferramenta no resumo |
| `types` | tipos agregados por repositório |

### 7.9 Alvo do ML — `security_dataset.csv`

| Coluna | O que mede / interpretar |
|---|---|
| `has_security_risk` | **alvo (0/1)**: 1 se Semgrep **ou** CodeQL sinaliza o arquivo (união) |
| `n_semgrep` / `n_codeql` | nº de achados por ferramenta — **só para concordância; excluídas das features** (`SKIP_COLS` em `ml_security_pipeline.py`) |

---

## 8. Arquivos CSV na pasta `data/`

### 8.1 Ordem de geração

A ordem segue exatamente a lista `PHASES` de `run_all.py`. Os 4 primeiros blocos
são **independentes** (só precisam dos clones); os 3 últimos são **derivados**.

| # | Fase / script | CSV(s) gerado(s) | Tipo |
|---|---|---|---|
| 0 | `search_repositories.py` (apoio, **fora do fluxo**) | `repositories.csv` | metadados |
| 1 | `clone_repositories.py` | *(nenhum CSV — popula `repos/`)* | — |
| 2 | `collect_loc_metrics.py` | `loc.csv` | coleta |
| 3 | `collect_complexity_metrics.py` | `complexity.csv` | coleta (fallback) |
| 4 | `collect_sonarqube_metrics.py` | `sonarqube.csv` | coleta (canônico) |
| 5 | `collect_semgrep_metrics.py` | `semgrep_findings.csv` | coleta (alvo) |
| 6 | `collect_codeql_metrics.py` | `codeql_findings.csv` | coleta (alvo) |
| 7 | `collect_pydriller_metrics.py` | `pydriller_metrics.csv` | coleta (feature) |
| 8 | `collect_ck_metrics.py` | `ck_metrics.csv` | coleta (feature) |
| 9 | `collect_osv_metrics.py` | `osv_findings.csv`, `osv_summary.csv` | coleta (descritivo) |
| 10 | `collect_gitleaks_metrics.py` | `secrets_findings.csv`, `secrets_summary.csv` | coleta (descritivo) |
| 11 | `build_security_dataset.py` | `security_dataset.csv` (+ `dataset_dictionary.md`) | **derivado** (junta tudo) |
| 12 | `ml_security_pipeline.py` | *(lê o dataset; escreve em `reports/`)* | consumo |

### 8.2 Por que essa ordem/padrão

- **`clone` primeiro:** todos os coletores iteram `repos/` via
  `common.iter_repo_dirs()` — sem os clones, não há o que medir.
- **Coletores independentes no meio:** cada um lê os fontes e escreve **um CSV
  por dimensão**, isolando uma preocupação (LOC, estrutura, OO, processo, SAST,
  SCA, segredos). Isso reflete a regra metodológica **"uma fonte por dimensão"**
  (evita dupla contagem/multicolinearidade).
- **`dataset` como barreira de agregação:** `build_security_dataset.py` só faz
  sentido depois que todos os CSVs de coleta existem, pois faz *merge* em nível
  de arquivo (`repository` + `file`), constrói o **alvo união** (Semgrep ∪
  CodeQL) e escolhe a fonte estrutural (SonarQube **ou** lizard).
- **`ml` por último (consumo):** depende apenas do `security_dataset.csv`
  consolidado; daí o dataset precisar estar pronto antes.

### 8.3 Conteúdo de cada CSV (colunas reais dos cabeçalhos)

| CSV | Colunas | Papel |
|---|---|---|
| `repositories.csv` | `full_name, url, stars, forks, open_issues, language, license, pushed_at, archived, description` | metadados GitHub (descritivo da seleção) |
| `loc.csv` | `repository, files, blank, comment, code, java_files, java_code, java_comment, java_blank` | normalização KLOC |
| `complexity.csv` | `repository, file, method, nloc, ccn, tokens, parameters, length` | complexidade por **método** (lizard) |
| `sonarqube.csv` | `repository, file, ncloc, lines, functions, classes, statements, complexity, cognitive_complexity, duplicated_lines, duplicated_lines_density, duplicated_blocks, comment_lines, comment_lines_density, code_smells, sqale_index, sqale_debt_ratio, violations, blocker_violations, critical_violations, major_violations, minor_violations` | estrutura/dívida por **arquivo** (canônico) |
| `semgrep_findings.csv` | `repository, file, rule_id, severity, cwe, message` | achados SAST (alvo) |
| `codeql_findings.csv` | `repository, file, rule_id, severity, cwe, message` | achados SAST (alvo, união) |
| `pydriller_metrics.csv` | `repository, file, commits, distinct_authors, lines_added, lines_removed, churn, file_age_days, days_since_change` | processo (feature) |
| `ck_metrics.csv` | `repository, file, wmc, dit, noc, cbo, rfc, lcom, lcom_star, num_methods, num_static_methods, num_fields, num_static_fields, tcc, lcc, num_classes` | OO (feature) |
| `osv_findings.csv` | `repository, package_name, version, vuln_id, severity_score, severity_label, title` | SCA por CVE (descritivo) |
| `osv_summary.csv` | `repository, deps_declared, deps_queryable, vulns_direct, vulns_critical, vulns_high, vulns_medium, vulns_low, avg_cvss` | SCA por repo (descritivo) |
| `secrets_findings.csv` | `repository, file, secret_type, line_number, detected_by` | segredos por achado (descritivo) |
| `secrets_summary.csv` | `repository, files_with_secrets, total_secrets, by_gitleaks, by_detect_secrets, by_both, types` | segredos por repo (descritivo) |
| `security_dataset.csv` | `repository, file, n_semgrep, n_codeql, has_security_risk` + 20 colunas `sonar_*` + 14 OO (CK) + 7 de processo (PyDriller) | **entrada do ML** (alvo + features) |

> O significado de cada coluna está nas tabelas da Seção 7. O dicionário
> completo gerado pelo pipeline está em `data/dataset_dictionary.md`.

---

## 9. Machine Learning — em detalhe (`ml_security_pipeline.py`)

Esta é a etapa que responde à **pergunta de pesquisa** declarada no topo do
script:

> *"Métricas de qualidade de código (complexidade, duplicação, code smells,
> métricas de processo e métricas OO) conseguem **prever** quais arquivos `.java`
> são propensos a risco de segurança?"*

Ou seja: o ML **não** olha para o conteúdo de segurança do arquivo. Ele tenta
descobrir se *características de qualidade/estrutura/histórico* (que **não** têm
nada a ver com segurança) são suficientes para **antecipar** que um arquivo será
sinalizado pelos SAST. Se conseguir, validamos a hipótese (central na norma ISO/
IEC 25010) de que **manutenibilidade ruim correlaciona com risco de segurança**.

### 9.1 A métrica-alvo (target) e por que foi escolhida

| Item | Valor |
|---|---|
| **Coluna alvo** | `has_security_risk` (binária: 0 ou 1) |
| **Como é definida** | `1` se o arquivo foi sinalizado pelo **Semgrep OU pelo CodeQL** (**união**); `0` caso contrário |
| **Tipo de problema** | Classificação binária |
| **Dimensão ISO/IEC 25010** | **Segurança** (*Security*) |

**Por que esse alvo?**

1. **Mapeia direto para a dimensão "Segurança" da ISO/IEC 25010** — é a
   característica de qualidade que o estudo quer prever; as demais métricas
   (manutenibilidade, confiabilidade) viram *features*.
2. **União (Semgrep ∪ CodeQL) e não interseção** — escolha deliberada para
   **maximizar o recall**. Em segurança, o pior erro é o **falso-negativo**
   (deixar passar um arquivo arriscado). Marcar como "arriscado" se *qualquer*
   uma das duas ferramentas SAST apontar reduz a chance de "esquecer" um arquivo
   de verdade perigoso (documentado em `build_security_dataset.py`, cabeçalho).
3. **Dois SAST independentes** (Semgrep e CodeQL) dão robustez: as colunas
   `n_semgrep` e `n_codeql` ficam no dataset **só para análise de concordância**
   entre as ferramentas — **não** entram como features (ver anti-vazamento).

### 9.2 As features selecionadas (o que o modelo "vê")

O script monta a matriz de features assim (`prepare()`):
*todas as colunas, menos as de identificação/alvo, mantendo só as numéricas.*

```python
SKIP_COLS = {"repository", "file", "has_security_risk", "n_semgrep", "n_codeql"}
feature_cols = [c numérica  para c em colunas  se c não está em SKIP_COLS]
X = df[feature_cols].fillna(0)        # NaN → 0
y = df["has_security_risk"]
groups = df["repository"]             # usado pelo GroupKFold
```

Resultado: **41 features numéricas**, organizadas em 3 famílias, todas mapeadas à
ISO/IEC 25010 (detalhe coluna-a-coluna na Seção 7 e em `dataset_dictionary.md`):

| Família | Nº | Origem | Dimensão ISO 25010 | Exemplos |
|---|---|---|---|---|
| Estruturais | **20** | SonarQube (`sonar_*`) | Manutenibilidade | `sonar_complexity`, `sonar_cognitive_complexity`, `sonar_code_smells`, `sonar_sqale_index`, `sonar_duplicated_lines_density` |
| Orientação a objetos | **14** | CK | Manutenibilidade / Confiabilidade | `wmc`, `cbo`, `rfc`, `lcom`, `dit`, `tcc` |
| Processo (histórico git) | **7** | PyDriller | Manutenibilidade | `commits`, `distinct_authors`, `churn`, `file_age_days`, `days_since_change` |

> **Regra anti-vazamento (anti-leakage), declarada no código:** **nenhuma**
> métrica derivada de segurança pode ser feature. Por isso (a) `n_semgrep`/
> `n_codeql` são excluídas (seriam circulares — derivam do próprio alvo), e (b)
> as medidas de *segurança* do SonarQube **nunca são coletadas**. O modelo só
> enxerga qualidade/estrutura/processo — jamais "pistas" do alvo. Sem isso, os
> resultados seriam artificialmente perfeitos e cientificamente inválidos.

### 9.3 O dataset em números (estado atual)

| Métrica | Valor real |
|---|---|
| Linhas (arquivos `.java`) | **31.622** |
| Repositórios (grupos) | **10** (NSA) |
| Positivos (`has_security_risk=1`) | **560** |
| Taxa de positivos | **≈ 1,77 %** → **fortemente desbalanceado** |
| Features | **41 numéricas** |

> Os repositórios têm tamanhos muito diferentes (ghidra ≈ 23,1 mil arquivos;
> datawave ≈ 6,1 mil; os menores com < 200). Isso reforça a necessidade de
> validar **por repositório** (Seção 9.4), e não por arquivo solto.

### 9.4 Como o modelo é treinado e como se separam treino e teste

Este é o ponto metodológico mais importante e responde diretamente à pergunta
*"como ocorreu a separação entre dados de teste e dados reais?"*.

**Não há um *split* aleatório 70/30.** A validação usa
**`GroupKFold(n_splits=5)` agrupado por repositório** (`cross_validate()`):

```
GroupKFold (5 dobras), agrupado por "repository"
┌─────────────────────────────────────────────────────────────┐
│ Dobra k:  treina nos arquivos de  N-1 repositórios            │
│           testa  nos arquivos do(s) repositório(s) restante(s)│
│           → um repositório NUNCA aparece em treino e teste    │
│             ao mesmo tempo                                     │
└─────────────────────────────────────────────────────────────┘
```

**Por que agrupar por repositório (e não dividir arquivos aleatoriamente)?**
Para **impedir vazamento de informação intra-repositório**. Arquivos do mesmo
projeto compartilham estilo, autores e padrões; se uns fossem para treino e
outros (do mesmo repo) para teste, o modelo "decoraria" o projeto e o resultado
seria otimista demais. Testando em um **repositório inteiro nunca visto**, mede-se
a capacidade real de **generalizar para um projeto novo** — que é o uso prático.

**Sobre "dados de teste × dados reais":** a dobra de teste é sempre composta de
**arquivos reais, intocados** — nenhuma amostra sintética entra na avaliação. O
único dado artificial do pipeline é o **SMOTE**, aplicado **exclusivamente na
dobra de treino** (ver abaixo). Portanto: **treino = reais + sintéticos (SMOTE);
teste = 100 % reais**. O script ainda **pula** qualquer dobra cujo conjunto de
teste tenha só uma classe (sem positivos não dá para medir).

**Sequência exata dentro de cada dobra** (`cross_validate`):

1. **Separação** treino/teste pelos índices que o `GroupKFold` devolve.
2. **Padronização** (`StandardScaler`): ajustada **só no treino** e aplicada ao
   teste (evita vazamento de escala). Usada **apenas** pela Regressão Logística;
   os modelos de árvore usam os dados sem escalonar.
3. **Balanceamento com SMOTE** (`imbalanced-learn`): gera positivos sintéticos
   **só no treino** (`k_neighbors = min(5, nº_positivos − 1)`), nunca no teste.
   Em conjunto com `class_weight="balanced"` nos modelos, ataca o desbalanceamento
   de 1,77 %.
4. **Treino e predição** de cada um dos 5 modelos; coleta de probabilidades
   (`predict_proba`) para a curva ROC.
5. **Métricas da dobra**: precisão, recall, F1, ROC-AUC e a matriz de confusão
   (TP/FP/FN/TN).

Ao final, as métricas das 5 dobras são **promediadas** por modelo
(`aggregate_results`) → `reports/ml_results.csv`.

### 9.5 Os 5 modelos comparados (`build_models`)

Todos com `random_state=42` (reprodutível) e tratamento de classe desbalanceada:

| Modelo | Hiperparâmetros principais | Desbalanceamento | Escalona? |
|---|---|---|---|
| **LogisticRegression** | `max_iter=1000` | `class_weight="balanced"` | **Sim** (StandardScaler) |
| **DecisionTree** | `max_depth=10` | `class_weight="balanced"` | Não |
| **RandomForest** | `n_estimators=200` | `class_weight="balanced"` | Não |
| **XGBoost** | `n_estimators=200`, `eval_metric="logloss"` | (boosting) | Não |
| **LightGBM** | `n_estimators=200` | `class_weight="balanced"` | Não |

### 9.6 Métricas de avaliação — e por que **não** usamos *accuracy*

Com apenas 1,77 % de positivos, um classificador que dissesse "**nenhum** arquivo
é arriscado" acertaria ≈ 98 % — *accuracy* alta e **inútil**. Por isso o estudo
mede (docstring do script):

- **Recall** — dos arquivos realmente arriscados, quantos o modelo pega (o que
  mais importa em segurança).
- **Precision** — dos que o modelo aponta, quantos são de fato arriscados.
- **F1** — média harmônica de precisão e recall.
- **ROC-AUC** — poder de ranqueamento independente de limiar (a métrica
  principal de comparação entre modelos).

### 9.7 Resultados atuais (`reports/ml_results.csv`, média das dobras)

| Modelo | Precision | Recall | F1 | **ROC-AUC** |
|---|---|---|---|---|
| LogisticRegression | 0,089 | **0,644** | 0,155 | 0,785 |
| DecisionTree | 0,098 | 0,408 | 0,150 | 0,719 |
| **RandomForest** | 0,385 | 0,166 | **0,195** | **0,859** |
| XGBoost | 0,319 | 0,136 | 0,168 | 0,820 |
| LightGBM | 0,341 | 0,121 | 0,155 | 0,837 |

**Leitura para a banca:**
- **RandomForest é o melhor modelo geral** (ROC-AUC ≈ **0,859** e maior F1) —
  ROC-AUC bem acima de 0,5 (acaso) **confirma** que as métricas de qualidade
  **têm sim poder preditivo** sobre risco de segurança.
- A **Regressão Logística** entrega o **maior recall** (0,64): pega mais arquivos
  arriscados, ao custo de muitos falsos-positivos (precisão baixa) — útil se o
  objetivo for "não deixar passar nada" para triagem manual.
- Os valores absolutos de F1/precision são modestos — esperado num problema
  **raro (1,77 %) e validado entre projetos diferentes** (cenário propositalmente
  difícil e honesto, sem vazamento).

### 9.8 Interpretabilidade — quais features pesam mais

Após a validação cruzada, o script treina **um RandomForest no dataset inteiro**
(`rf_full`) só para explicar o modelo, e gera dois artefatos:

- **Importância de Gini** (`charts/feature_importance_rf.png`) — top 20 features
  por ganho de impureza no RF.
- **SHAP** (`charts/shap_summary.png`) — `TreeExplainer` sobre uma amostra de até
  2000 arquivos; mostra *direção* e *magnitude* do efeito de cada feature na
  predição (beeswarm), bem mais informativo que o Gini.

### 9.9 Saídas geradas pela etapa de ML

| Arquivo | O que contém |
|---|---|
| `reports/ml_results.csv` | Métricas agregadas (média das dobras) por modelo — tabela da Seção 9.7 |
| `reports/ml_confusions.csv` | Matriz de confusão (TP/FP/FN/TN) **por dobra e por modelo** (25 linhas = 5 modelos × 5 dobras) |
| `reports/charts/roc_curves.png` | Curvas ROC de todos os modelos (dobras concatenadas) |
| `reports/charts/model_comparison.png` | Barras comparando F1 e ROC-AUC |
| `reports/charts/feature_importance_rf.png` | Top 20 features (Gini, RandomForest) |
| `reports/charts/shap_summary.png` | Resumo SHAP (beeswarm) do RandomForest |

### 9.10 Como rodar **somente** o Machine Learning

```powershell
# Opção A — pelo orquestrador (recomendado)
python scripts/run_all.py --only ml

# Opção B — direto o módulo
python scripts/ml_security_pipeline.py

# Pré-requisito: data/security_dataset.csv já deve existir.
# Se ainda não foi gerado (ou as coletas mudaram), gere antes:
python scripts/run_all.py --only dataset
# Encadeado (dataset + ml de uma vez):
python scripts/run_all.py --only dataset,ml
```

Ao terminar, confira `reports/ml_results.csv` e as imagens em
`reports/charts/`. O resumo dos modelos também é impresso no log
(`_print_summary`).

---

### Observações finais de precisão

- **⚠️ Não determinado pelo código:** o número exato de regras/CWEs que o
  `--config auto` do Semgrep aplica (depende da versão do Semgrep em runtime).
- **⚠️ Não determinado pelo código:** a versão do servidor SonarQube não é
  fixada por nenhum arquivo do pipeline — vem da imagem Docker baixada
  (documentada como 26.6.0 em `TOOLS_VERSIONS.md`).
- `repositories.csv` é produzido por um script de apoio (`search_repositories.py`)
  cuja **fonte `.py` não está versionada** (só o `.pyc`); por isso não é
  reexecutável a partir do estado atual do repositório.
