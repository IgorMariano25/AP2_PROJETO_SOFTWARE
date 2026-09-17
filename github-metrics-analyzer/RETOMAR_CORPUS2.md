# Como retomar a execução do Corpus 2

Estado em **2026-09-17**. O pipeline está sendo executado por etapas, em
dias diferentes, de propósito.

---

## 1. O que já está pronto

| Fase | Saída em `data/` | Situação |
|---|---|---|
| `clone` | `repos/` — 10 repos, **25.567** arquivos `.java` | completa |
| `loc` | `loc.csv` | completa — **com `cloc` de verdade** pela 1ª vez |
| `complexity` | `complexity.csv` — 212.850 métodos | completa |
| `sonarqube` | `sonarqube.csv` — 32.671 linhas (25.567 `.java`) | completa e corrigida |
| `semgrep` | `semgrep_findings.csv` — **1.230** achados, 10/10 repos | completa (37 min) |
| `codeql` | `codeql_findings.csv` — **1.875** achados em 617 arquivos | completa (2h26min) |
| `ck` | `ck_metrics.csv` — **24.694** arquivos, 10/10 repos (91–100%) | completa (ver §7.2) |
| `osv` | `osv_findings.csv` — 7 CVEs; `osv_summary.csv` — 10 repos | completa (18 s) |
| `secrets` | `secrets_findings.csv` — **3.803** segredos únicos | completa (13 min) |

Comparação com o corpus NSA: Semgrep 1.230 vs 575; CodeQL 1.875 vs 1.045. O
corpus novo tem cerca do dobro de achados, que era a expectativa ao escolher
repositórios com superfície de segurança mais rica.

## 2. O que falta — plano acordado

~~1. **2026-09-17:** `ck`, `osv`, `secrets`.~~ **concluído**

2. **Próximo passo:** `pydriller` sozinho — foi interrompido de propósito em
   2026-09-17 e **não gravou** o `pydriller_metrics.csv`.
3. **Depois que o PyDriller terminar:** `dataset` → `ml` → `report`.

```powershell
# amanhã, passo 2
.\.venv\Scripts\python.exe scripts\run_all.py --only pydriller
# depois, passo 3
.\.venv\Scripts\python.exe scripts\run_all.py --only dataset,ml,report
```

> **Não rode `dataset` antes do PyDriller.** Sem o `pydriller_metrics.csv`, o
> dataset sai sem a dimensão de **processo** (`commits`, `distinct_authors`,
> `lines_added`, `lines_removed`, `churn`, `file_age_days`,
> `days_since_change`) — uma das três famílias de features do estudo, ao lado
> das estruturais (SonarQube) e das OO (CK). O pipeline degrada graciosamente
> e não quebra; ele apenas produz um modelo cego para essa dimensão, e o
> `feature_importance_rf.png` e o SHAP sairiam incompletos.

`data/` contém **apenas dados do Corpus 2**. Os 9 CSVs dessas fases, que ainda
tinham os dados da NSA, foram movidos para `data_nsa_stale/` — não apagados.

> **Por que isso importa se você rodar por etapas.** O universo de linhas do
> dataset é a **união** dos pares `(repository, file)` de todas as tabelas de
> features ([`build_security_dataset.py:197-202`](scripts/build_security_dataset.py#L197-L202)),
> não uma lista fixa de repositórios. Se a fase `dataset` rodasse com
> `ck_metrics.csv` e `pydriller_metrics.csv` ainda cheios de linhas da NSA,
> esses arquivos entrariam no `security_dataset.csv` misturados aos novos — e
> sobreviveriam ao filtro da linha 251, porque têm features preenchidas.
> Com os CSVs antigos fora de `data/`, uma execução prematura de `dataset`
> apenas produz menos dados, em vez de misturar os dois corpora.

---

## 3. Pré-requisitos antes de retomar

### 3.1 Subir o SonarQube

O container existe mas está parado. Os dados das análises estão no volume, e o
`SONAR_TOKEN` do `.env` continua válido:

```powershell
docker start sonarqube
# aguarde status UP:
while ((Invoke-RestMethod http://localhost:9000/api/system/status).status -ne "UP") { Start-Sleep 10 }
```

Só é necessário se for **re-rodar a fase `sonarqube`**. Para as fases que faltam
(`semgrep` em diante), o servidor não é usado — o `sonarqube.csv` já está pronto.

Credenciais do servidor: usuário `admin`, senha `AP2sonar!2026` (a senha padrão
`admin` foi rotacionada ao criar o container; a rotação é obrigatória no
primeiro login).

### 3.2 PATH com o `cloc`

O `cloc` não está instalado no sistema — foi baixado para
`developer-tools/cloc/`. Só importa para a fase `loc` (já concluída), mas vale
manter no PATH:

```powershell
$env:PATH = "E:\AP2-Projeto-ES\github-metrics-analyzer\developer-tools\cloc;$env:PATH"
```

### 3.3 Rede sem sandbox

O `GITHUB_TOKEN` do `.env` estava válido (5.000 req/h). As fases `osv` e
`codeql` (download de query packs) precisam de internet.

---

## 4. Comando para retomar

```powershell
cd E:\AP2-Projeto-ES\github-metrics-analyzer
$env:PATH = "E:\AP2-Projeto-ES\github-metrics-analyzer\developer-tools\cloc;$env:PATH"
.\.venv\Scripts\python.exe scripts\run_all.py --only semgrep,codeql,pydriller,ck,osv,secrets,dataset,ml,report
```

Por etapas, se preferir acompanhar cada uma:

```powershell
.\.venv\Scripts\python.exe scripts\run_all.py --only semgrep
.\.venv\Scripts\python.exe scripts\run_all.py --only codeql      # a mais longa
.\.venv\Scripts\python.exe scripts\run_all.py --only pydriller,ck
.\.venv\Scripts\python.exe scripts\run_all.py --only osv,secrets
.\.venv\Scripts\python.exe scripts\run_all.py --only dataset,ml,report
```

Tempos observados nas fases já rodadas, como referência de ordem de grandeza:
`loc` 3 min, `complexity` 2 min, `sonarqube` 44 min, `semgrep` 37 min,
`codeql` **2h26min** (de longe a mais cara — cria um banco por repositório).

---

## 5. Onde está o corpus NSA antigo

Nada foi perdido. Três cópias:

- **Commit `b37ad22`** — congela todos os CSVs, charts e relatórios do estudo NSA.
- **`data_nsa/` e `reports_nsa/`** — cópias locais (gitignored, já que o git guarda o conteúdo).
- **`repos_nsa/`** — os 10 clones da NSA, movidos para fora de `repos/` para que
  os coletores não os varram. A lista original está em `repos_nsa.txt`.
- **`data_nsa_stale/`** — os 9 CSVs da NSA que ocupavam `data/` e ainda não
  haviam sido regerados (ver §2). Duplicam o conteúdo de `data_nsa/`; existem
  só para deixar `data/` contendo exclusivamente o Corpus 2.

**Não é necessário reexecutar nada do corpus NSA** — os resultados dele estão
completos e preservados. As fases pendentes rodam exclusivamente sobre os 10
repositórios novos.

Os coletores iteram sobre os diretórios em `repos/`, **não** sobre o
`repos.txt` — por isso mover os clones foi necessário, e não bastou editar a
lista.

---

## 6. Pendências metodológicas em aberto

### 6.1 Critério #1 (Java ≥ 70%) — 4 dos 10 repos falham

Com o `cloc` funcionando pela primeira vez, foi possível verificar o critério
com dados reais:

| Repositório | % Java | LOC Java | #1 (≥70%) | #6 (10k–400k) |
|---|---|---|---|---|
| thingsboard/thingsboard | 30,6% | 406.675 | ✗ | ✗ acima |
| jenkinsci/jenkins | 56,8% | 208.525 | ✗ | ok |
| apache/zookeeper | 60,6% | 126.691 | ✗ | ok |
| alibaba/nacos | 64,4% | 532.685 | ✗ | ✗ acima |
| apache/shiro | 71,2% | 44.241 | ok | ok |
| apache/commons-compress | 89,8% | 83.324 | ok | ok |
| apache/dubbo | 91,9% | 309.434 | ok | ok |
| netty/netty | 92,0% | 429.953 | ok | ✗ acima |
| apache/rocketmq | 93,4% | 287.384 | ok | ok |
| apache/httpcomponents-client | 95,3% | 119.649 | ok | ok |

A causa é frontend e configuração (thingsboard tem UI Angular grande; jenkins
tem muito JS e Jelly). **Não invalida a análise** — a unidade de análise é o
arquivo `.java` e os coletores só olham para esses. O que fica comprometido é a
afirmação "corpus Java-dominante" no artigo, se sustentada pelo critério do
`CRITERIOS_SELECAO_REPOSITORIOS.md`. Decisão pendente: reformular o critério,
trocar repositórios, ou registrar como limitação de validade.

### 6.2 Artigo e RESUME.md ainda descrevem o corpus NSA

`Artigo/main.tex` e `RESUME.md` trazem os números antigos (31.622 arquivos,
1,77% de positivos, tabela de ROC-AUC do corpus NSA). Decisão pendente:
atualizar os dois quando os novos resultados saírem, ou tratar o Corpus 2 como
estudo separado.

---

## 7. Bugs corrigidos

### 7.1 Truncamento silencioso no coletor SonarQube

`scripts/collect_sonarqube_metrics.py` — a paginação do `component_tree`
tratava uma página que falhou como fim dos dados, truncando as medidas em
silêncio. O `alibaba/nacos` entrou com **948** de 5.249 arquivos `.java`, e o
único sinal no log era um `1000 files with measures`, sem erro.

Correções: `_api_get` ganhou retry com backoff exponencial e timeout de 180s
(uma página de 500 componentes num projeto de 5k arquivos leva mais de 60s para
o servidor montar), e a paginação agora registra `measures are INCOMPLETE` em
nível de erro em vez de encerrar silenciosamente.

Após a correção, os 10 repositórios batem exatamente com a contagem de `.java`
em disco.

### 7.2 CK produzindo zero linhas para um repositório inteiro

O CK 0.7.0 parseia o repositório todo num único lote de `ASTParser`, então
**um** arquivo irresolvível aborta a execução inteira com um
`NullPointerException` do JDT (`TypeBinding.kind() ... receiverType is null`) e
o repositório sai com zero registros.

No Corpus 2 isso atingiu o `thingsboard/thingsboard`: 4.780 arquivos `.java` e
**0 linhas** no `ck_metrics.csv`, com o log registrando apenas
`CK non-zero exit` seguido de `0 file records`. O gatilho é uma *switch
expression* (Java 14+) que o JDT embutido não consegue resolver. O mesmo bug
já havia atingido o `ghidra` no Corpus 1.

**Correção:** `scripts/collect_ck_partitioned.py`, que generaliza o
`collect_ck_ghidra.py` (fixo no ghidra) para qualquer repositório:

```powershell
.\.venv\Scripts\python.exe scripts\collect_ck_partitioned.py --repo thingsboard/thingsboard
```

Roda o CK uma vez por raiz de módulo (`**/src/main/java`, `**/src/test/java`),
de modo que uma falha perde só aquele módulo. É retomável (parciais em
`data/partial/ck_<repo>/`) e substitui as linhas daquele repositório no
`ck_metrics.csv`.

**Sem mudança metodológica:** mesma ferramenta, mesmas métricas, mesma
agregação classe→arquivo do `collect_ck_metrics.py`. Só o particionamento do
lote de parsing muda. Raízes que falhem ficam registradas como ausentes,
nunca fabricadas como zero.

Resultado no thingsboard: 63 raízes, **0 falharam**, 4.457 arquivos (93%) —
dentro da faixa dos outros 9 repositórios (91–100%). A lacuna residual em todos
eles são arquivos sem classe parseável (`package-info.java`, interfaces vazias,
anotações), comportamento normal do CK.

> Para comparação: no Corpus 1 o `ck_metrics.csv` tinha 5.530 linhas para
> 31.622 arquivos (17%), porque o ghidra dominava o corpus e travava do mesmo
> jeito. No Corpus 2 são 24.694 para 25.567 (97%).
