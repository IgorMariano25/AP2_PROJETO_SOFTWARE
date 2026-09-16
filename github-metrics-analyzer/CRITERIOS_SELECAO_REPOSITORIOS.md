# Critérios de Seleção de Repositórios

**As 10 características obrigatórias para que um repositório GitHub seja analisável pelo pipeline `github-metrics-analyzer`**

---

## Sobre este documento

Os critérios abaixo **não são preferências metodológicas** — cada um é uma dependência dura do código em [`scripts/`](scripts/). Se um repositório violar qualquer um deles, o resultado não é um erro visível: é uma coluna vazia, um *fold* de validação descartado ou uma métrica constante que degrada o modelo em silêncio.

Qualquer repositório público do GitHub que satisfaça as 10 características pode ser analisado — **não há restrição de organização, domínio ou nicho**. O corpus original (10 repositórios Java da `NationalSecurityAgency`) foi uma escolha de conveniência, não uma exigência técnica.

**Escopo:** repositórios públicos, exclusivamente do GitHub, com relevância na comunidade técnica.

---

## 1. Java como linguagem dominante (≥ 70% do LOC), em `.java` puro

O pipeline é **Java-only por construção**. Não há caminho de configuração para outra linguagem.

| Ferramenta | Evidência no código |
|---|---|
| CK (métricas OO) | parseia apenas fonte Java — [`collect_ck_metrics.py:116`](scripts/collect_ck_metrics.py#L116) |
| CodeQL (SAST) | `--language=java` fixo — [`collect_codeql_metrics.py:102`](scripts/collect_codeql_metrics.py#L102) |
| PyDriller (processo) | `only_modifications_with_file_types=[".java"]` — [`collect_pydriller_metrics.py:54`](scripts/collect_pydriller_metrics.py#L54) |
| lizard (complexidade) | `rglob("*.java")` — [`collect_complexity_metrics.py:24`](scripts/collect_complexity_metrics.py#L24) |
| LOC | coluna `java_code` — [`collect_loc_metrics.py:28`](scripts/collect_loc_metrics.py#L28) |

A unidade de análise do dataset é o **arquivo `.java`** ([`build_security_dataset.py`](scripts/build_security_dataset.py)).

**Excluir:** repositórios majoritariamente Kotlin, Scala, Groovy, ou projetos Android dominados por XML/JNI.
**Sintoma da violação:** o clone funciona, todas as fases "passam", e o `security_dataset.csv` sai **vazio**.

---

## 2. Repositório público no GitHub, clonável anonimamente, no formato `owner/repo`

O clone monta a URL diretamente: `https://github.com/{full_name}.git` ([`clone_repositories.py:16`](scripts/clone_repositories.py#L16)). O `repos.txt` aceita uma entrada `owner/repo` por linha. Apenas diretórios contendo `.git` são iterados ([`common.py:107-113`](scripts/common.py#L107-L113)).

### ⚠️ Detalhe crítico — nomes com duplo underscore

A pasta local é nomeada `owner__repo`, e a conversão reversa troca `__` por `/`:

```python
def repo_to_folder(full_name): return full_name.replace("/", "__")
def folder_to_repo(folder_name): return folder_name.replace("__", "/")
```
[`common.py:99-104`](scripts/common.py#L99-L104)

**Um repositório cujo nome contenha `__` corrompe a coluna `repository`** em todos os CSVs e quebra o *merge* final do dataset, além do agrupamento do `GroupKFold`.

**Excluir também:** repositórios que dependem de Git LFS ou de submódulos — o clone não traz esse conteúdo, e os `.java` referenciados simplesmente não existirão no disco.

---

## 3. Histórico Git completo, longo e com múltiplos autores

Sete features de ML vêm do histórico: `commits`, `distinct_authors`, `lines_added`, `lines_removed`, `churn`, `file_age_days`, `days_since_change`. O clone é **intencionalmente sem `--depth`** para preservar o histórico completo.

### Limiares recomendados

- ≥ **300 commits**
- ≥ **5 autores distintos**
- ≥ **2 anos** de atividade
- commits que tocaram arquivos `.java` **repetidamente** ao longo do tempo

**Excluir:** repositórios com histórico *squashed* ou importados de outro VCS em um único "initial commit".

**Sintoma da violação:** todos os arquivos recebem `commits = 1`, `distinct_authors = 1`, `file_age_days = 0`. As sete colunas de processo viram constantes — a dimensão inteira de métricas de processo é perdida, e com ela boa parte do poder preditivo do modelo.

---

## 4. Analisável sem build (*source-only*, zero compilação)

Todo o estudo é estático — nenhum projeto é compilado ou executado:

- SonarQube aponta `sonar.java.binaries` para o próprio diretório de fontes ([`collect_sonarqube_metrics.py:105`](scripts/collect_sonarqube_metrics.py#L105))
- CodeQL usa `--build-mode=none` ([`collect_codeql_metrics.py:102`](scripts/collect_codeql_metrics.py#L102))
- CK parseia AST de fonte, sem bytecode

**Excluir:** projetos em que parte relevante do código só existe **após** geração — Protobuf/gRPC, ANTLR, JAXB, *annotation processors* pesados, uso extensivo de Lombok.

**Sintoma da violação:** os arquivos gerados não estão no clone. O dataset fica com buracos estruturais e o CK **subestima sistematicamente** o acoplamento (CBO/RFC), porque as classes geradas que fecham o grafo de dependências não existem.

---

## 5. Manifestos Maven ou Gradle com versões literais e fixadas

O coletor de SCA (análise de composição) reconhece exclusivamente `pom.xml`, `build.gradle` e `build.gradle.kts` ([`collect_osv_metrics.py:126-141`](scripts/collect_osv_metrics.py#L126-L141)).

Ele **descarta qualquer versão iniciada por `$`** ([`collect_osv_metrics.py:84-86`](scripts/collect_osv_metrics.py#L84-L86)), porque a API OSV exige versão exata:

```python
if v.startswith("$"):
    v = ""   # ${spring.version} → não consultável
```

O regex de dependências Gradle captura apenas o formato literal `grupo:artefato:versão` ([`collect_osv_metrics.py:100-104`](scripts/collect_osv_metrics.py#L100-L104)).

**Excluir:**

- builds **Ant**, **Bazel** ou **Make** (nenhum manifesto reconhecido → `deps_declared = 0`)
- projetos Gradle modernos com *version catalog* (`libs.versions.toml`) — `implementation(libs.netty)` não casa com o regex
- projetos que herdam 100% das versões de um BOM/parent POM → `deps_queryable = 0`

> **Limitação já documentada no estudo:** apenas dependências **diretas** são resolvidas. Transitivas exigiriam resolução completa de build.

---

## 6. Volume no ponto ótimo: ~200–5.000 arquivos `.java` (~10k–400k LOC Java)

Existe **piso e teto**. Ambos são rígidos.

### Piso

Poucos arquivos → linhas insuficientes para o `GroupKFold` e positivos insuficientes para o SMOTE, que exige `y_train.sum() > 1` ([`ml_security_pipeline.py:166`](scripts/ml_security_pipeline.py#L166)).

### Teto — timeouts codificados

| Fase | Timeout |
|---|---|
| `git clone` | 3600 s |
| Semgrep | 1800 s ([`collect_semgrep_metrics.py:67`](scripts/collect_semgrep_metrics.py#L67)) |
| CK | 1800 s ([`collect_ck_metrics.py:126`](scripts/collect_ck_metrics.py#L126)) |
| CodeQL (DB + analyze) | 3600 s cada |
| SonarScanner | 3600 s |
| **Fila de análise SonarQube** | **300 s** ([`collect_sonarqube_metrics.py:123`](scripts/collect_sonarqube_metrics.py#L123)) |

O limite de 300 s da fila do SonarQube é o gargalo mais estreito e o primeiro a estourar em repositórios grandes.

**Referência concreta:** o `ghidra` do corpus atual tem **15.589 arquivos / 2.046.208 LOC Java** ([`data/loc.csv`](data/loc.csv)) — muito acima do teto, e exatamente o caso que estoura tempo de execução e espaço em disco (bases CodeQL acumulam em `.tmp/`).

**Evitar:** monorepos como `elasticsearch`, `hadoop`, `flink`, `nifi`.

---

## 7. Superfície de segurança real — sem ela não há rótulo positivo

**Este é o requisito mais subestimado de todos.**

O alvo `has_security_risk` é a **união Semgrep ∪ CodeQL** ([`build_security_dataset.py:98`](scripts/build_security_dataset.py#L98)), usando as suítes `p/java`, `p/owasp-top-ten`, `p/java-spring` e `java-security-extended`. Essas regras procuram:

SQL injection · deserialização insegura · XXE · path traversal · criptografia fraca · TLS mal configurado · credenciais expostas · injeção de comando

Um repositório de matemática, algoritmos, estruturas de dados ou DSP puro gera **zero positivos**. O resultado no código:

```python
if len(np.unique(y_test)) < 2:
    log.warning("  Fold %d skipped: only one class in test set")
    continue
```
[`ml_security_pipeline.py:154-156`](scripts/ml_security_pipeline.py#L154-L156)

O *fold* inteiro é descartado. Com poucos repositórios, isso pode inviabilizar toda a validação cruzada.

### Exigir

Presença efetiva de: I/O de rede · HTTP/servlets · persistência/JDBC · criptografia · serialização · parsing de XML/JSON · autenticação/autorização.

### Meta prática

**≥ 1% e ≤ 30% dos arquivos com achado.** Abaixo de 1% não há sinal para treinar; acima de 30% o rótulo perde poder discriminante e o modelo aprende ruído de regra.

---

## 8. Código OO idiomático, com variância estrutural

O CK produz as features estruturais canônicas: **WMC, DIT, NOC, CBO, RFC, LCOM, LCOM\*, TCC, LCC**. Elas só têm variância se houver classes reais, herança, campos e métodos com corpo.

**Excluir:**

- repositórios compostos só de interfaces, DTOs ou POJOs gerados
- coleções didáticas de exemplos (dezenas de módulos com 2 classes triviais cada)
- código *vendorizado*, minificado ou copiado de terceiros

**Sintoma da violação:** CBO, LCOM e DIT quase constantes. O RandomForest não tem o que aprender, a importância Gini fica plana e o gráfico SHAP sai degenerado.

---

## 9. Higiene de encoding e de caminhos (restrição real do Windows)

- **UTF-8 obrigatório:** `sonar.sourceEncoding=UTF-8` está *hardcoded* ([`collect_sonarqube_metrics.py:110`](scripts/collect_sonarqube_metrics.py#L110)). Fontes em ISO-8859-1/Windows-1252 falham ou entram corrompidas no dataset.
- **Chave de junção estável:** o merge final é por `(repository, file)` com caminho relativo normalizado ([`build_security_dataset.py:234`](scripts/build_security_dataset.py#L234)). *Symlinks*, árvores duplicadas (`vendor/`, `third_party/` com cópias do mesmo código) e colisões que diferem apenas por maiúsculas/minúsculas quebram o *join* entre as tabelas de features.
- **Caminhos curtos:** o pipeline roda em `win32`. Caminhos com mais de 260 caracteres fazem CK e CodeQL falharem **em silêncio**.
- **Sem fixtures binárias grandes:** o diretório `.tmp/` já acumula bases CodeQL volumosas; binários no repositório agravam o consumo de disco sem gerar métrica alguma.

---

## 10. Corpus de ≥ 5 repositórios (ideal: 10) de organizações e domínios distintos, com licença OSI

A validação usa `GroupKFold` **agrupado por repositório**:

```python
gkf = GroupKFold(n_splits=min(5, len(np.unique(groups))))
```
[`ml_security_pipeline.py:139`](scripts/ml_security_pipeline.py#L139) — e o pipeline aborta com menos de 2 repositórios ([`ml_security_pipeline.py:309`](scripts/ml_security_pipeline.py#L309)).

Com 5 ou mais grupos independentes, cada *fold* testa em um repositório **nunca visto** no treino, o que é a garantia contra vazamento intra-repositório.

### ⚠️ Defeito metodológico do corpus atual

O próprio relatório gerado admite ([`generate_comparative_report.py:239-242`](scripts/generate_comparative_report.py#L239-L242)):

> Três repositórios (`datawave`, `datawave-query-service`, `datawave-audit-service`, `datawave-authorization-service`) pertencem ao ecossistema **DataWave** — variável de confusão / limitação de validade externa.

São **4 dos 10 repositórios** do mesmo ecossistema, mesma organização, mesmo estilo de código, mesmas convenções. Isso é uma variável de confusão que destrói a validade externa: o modelo aprende *o estilo de código de uma organização*, não "o que caracteriza código inseguro".

**Regra para o novo corpus:** **um repositório por organização**, com domínios variados (rede, mensageria, IAM, dados, CI, biblioteca utilitária). Licença OSI que permita análise e publicação dos resultados.

---

## Checklist rápido de triagem

| # | Critério | Verificação objetiva |
|---|---|---|
| 1 | Java dominante | `Java ≥ 70%` na barra de linguagens do GitHub |
| 2 | Público, clonável, `owner/repo` | `git clone` anônimo funciona; nome **sem** `__`; sem LFS/submódulos |
| 3 | Histórico rico | ≥ 300 commits, ≥ 5 autores, ≥ 2 anos, sem *squash* |
| 4 | Sem build | não depende de código gerado (protobuf/ANTLR/Lombok pesado) |
| 5 | Manifesto SCA | `pom.xml` ou `build.gradle` com versões **literais** |
| 6 | Volume | 200–5.000 arquivos `.java`; 10k–400k LOC Java |
| 7 | Superfície de segurança | rede/HTTP/JDBC/cripto/serialização presentes |
| 8 | Variância OO | classes com herança e métodos reais, não só DTOs |
| 9 | Higiene | UTF-8; caminhos < 260 chars; sem symlinks/árvores duplicadas |
| 10 | Corpus | ≥ 5 repos, **1 por organização**, domínios distintos, licença OSI |

---

## Candidatos que se encaixam no perfil

Todos públicos no GitHub, Java, build Maven, alta relevância na comunidade técnica, **organizações distintas**. Verificar cada um contra o checklist acima antes de fixar no `repos.txt`.

| Repositório | Domínio (superfície de segurança) |
|---|---|
| `netty/netty` | I/O de rede, TLS, codecs de protocolo |
| `apache/shiro` | framework de autenticação e autorização |
| `alibaba/nacos` | *service registry* + servidor de configuração (HTTP) |
| `apache/rocketmq` | broker de mensageria distribuída |
| `apache/zookeeper` | coordenação distribuída, ACLs |
| `apache/dubbo` | RPC e serialização (superfície clássica de deserialização) |
| `jenkinsci/jenkins` | servidor de CI, histórico extenso de CVEs |
| `apache/httpcomponents-client` | cliente HTTP/TLS |
| `apache/commons-compress` | parsing de arquivos (zip-slip, path traversal) |
| `thingsboard/thingsboard` | plataforma IoT (web + persistência) |
| `apache/skywalking` | APM, agentes e coleta de telemetria |
| `google/guava` | biblioteca base — útil como **contraste** de baixa densidade |

### Evitar, apesar da popularidade

| Repositório | Critério violado |
|---|---|
| `elastic/elasticsearch`, `apache/hadoop`, `apache/flink` | **#6** — muito acima do teto de volume |
| `spring-projects/spring-boot` | **#5 e #6** — Gradle *version catalog* + tamanho |
| `apache/tomcat` | **#5** — build Ant, sem manifesto reconhecido |
| `iluwatar/java-design-patterns` | **#7 e #8** — sem superfície de segurança, classes triviais |
| `square/okhttp`, `signalapp/*` | **#1** — migrados para Kotlin |

---

## Observações sobre o estado atual do código

1. **`search_repositories.py` não existe.** O [`clone_repositories.py:36`](scripts/clone_repositories.py#L36) orienta *"Run search_repositories.py first"*, mas esse script não está em [`scripts/`](scripts/). Hoje o `repos.txt` é preenchido manualmente.

2. **`cloc` não estava instalado na última coleta.** Em [`data/loc.csv`](data/loc.csv), `files == java_files` em todos os repositórios, o que indica que o contador Python de fallback (Java-only) foi usado em vez do `cloc` ([`collect_loc_metrics.py:73`](scripts/collect_loc_metrics.py#L73)). Instalar `cloc` no novo corpus para obter o denominador de LOC total correto — sem ele, não é possível verificar o critério **#1** (percentual de Java) a partir dos dados coletados.

---

*Documento derivado da leitura direta dos 17 scripts em [`scripts/`](scripts/). Cada critério cita a linha de código que o torna obrigatório.*
