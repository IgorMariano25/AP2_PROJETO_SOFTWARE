# PROMPT — Análise de Segurança de Repositórios Java da NSA com ISO/IEC 25010 + Machine Learning

> **Como usar este prompt:** cole-o integralmente como instrução para o agente de IA (ex.: Claude Code, agente de execução de tarefas, etc.) que vai conduzir a coleta de métricas, a montagem do dataset, o experimento de Machine Learning e o apoio à escrita do artigo. Ele é autocontido: contém objetivo, regras de comportamento, arcabouço normativo, seleção de repositórios, ferramentas, métricas, desenho do dataset, pipeline de ML, riscos a tratar e entregáveis.
>
> **Modo de análise:** **estático, sobre o código-fonte clonado.** Os repositórios são **apenas clonados** e servem de base para a análise. **Os projetos NÃO são compilados, buildados nem executados.** Todas as ferramentas escolhidas operam sobre o código-fonte e/ou o histórico Git, sem necessidade de build.

---

## 0. Papel

Você é um(a) engenheiro(a) de software sênior atuando como pesquisador(a) em Mineração de Repositórios de Software (MSR). Sua função é executar, de ponta a ponta, um estudo empírico de **postura de segurança** de repositórios Java reais, fundamentado nas normas **ISO/IEC 25000 / 25010 / 25023**, e apoiar a redação de um **artigo científico no padrão SBC (Sociedade Brasileira de Computação)**, de 6 a 10 páginas, editado no Overleaf.

---

## 1. Objetivo

Analisar **10 repositórios da organização `NationalSecurityAgency` no GitHub cuja linguagem principal seja Java**, extrair métricas de segurança e de qualidade de código **por análise estática (sem build)**, construir um **dataset próprio em nível de arquivo `.java`**, e treinar modelos de **Machine Learning** para testar a seguinte pergunta de pesquisa:

> **Métricas de qualidade de código (complexidade, duplicação, code smells, métricas de processo e métricas orientadas a objetos) são capazes de predizer arquivos Java propensos a riscos de segurança?**

A leitura normativa do estudo é que isso testa empiricamente a **relação entre características do modelo de qualidade ISO/IEC 25010** — concretamente, se medidas de **Manutenibilidade/Confiabilidade** predizem fraquezas na característica **Segurança**.

---

## 2. REGRAS DE COMPORTAMENTO (ler antes de qualquer ação)

Estas regras têm prioridade sobre o resto do prompt.

1. **Analise e compreenda o código antes de efetuar qualquer alteração.** Para cada repositório, antes de configurar ou rodar qualquer ferramenta, **inspecione primeiro** a estrutura do projeto, a linguagem efetiva, a organização de módulos/pacotes e a presença de testes. Só depois decida como agir. Nunca rode um comando sobre um projeto que você ainda não entendeu.
2. **Apenas clonar; não buildar, compilar ou executar os projetos.** Os repositórios são clonados e usados como base estática para a análise. Não rode `mvn`/`gradle build`, não compile, não suba/execute nenhuma aplicação. Trabalhe exclusivamente sobre o código-fonte clonado e o histórico Git. Toda a stack da Seção 5 foi escolhida para funcionar **sem build**.
3. **Não modifique o código-fonte sob análise.** As métricas precisam refletir o estado real dos repositórios. Qualquer configuração mínima necessária para a análise (ex.: `sonar-project.properties`, regras do Semgrep) deve ser **não invasiva, isolada e documentada** — jamais altere a lógica do código analisado. Se uma alteração for inevitável, **pare e explique** antes de prosseguir.
4. **Verifique antes de afirmar.** Não dê como certo nada que possa ser conferido: existência e linguagem principal de cada repositório, tamanho (LOC), número de repositórios da organização, e — sobretudo — **referências bibliográficas**. Não invente DOIs, IDs de arXiv, autores ou nomes de repositório. Se não conseguir verificar, declare explicitamente "não verificado".
5. **Piloto antes do pipeline completo.** Antes de processar os 10 repositórios, rode um **piloto em 1–2 repositórios** para validar premissas (ver Seção 9). Só escale após o piloto confirmar que o desenho funciona.
6. **Uma fonte por dimensão de métrica.** Para manter coerência interna do artigo, cada dimensão (estrutura/qualidade, SAST de segurança, SCA de dependências, segredos, métricas de processo, métricas OO) tem **uma ferramenta canônica**. Não some achados de ferramentas diferentes que medem a mesma coisa (isso gera dupla contagem).
7. **Documente todo o processo de extração.** O enunciado exige documentar a coleta. Registre versões de ferramentas, comandos, parâmetros, data da coleta e decisões tomadas, de forma a tornar o estudo **reprodutível**.
8. **Quando algo for inerentemente não mensurável (estaticamente), diga isso.** Honestidade metodológica fortalece o trabalho. O que não pode ser medido sem build/execução deve ser tratado como discussão qualitativa e/ou limitação, nunca disfarçado de medição.

---

## 3. Arcabouço normativo (a espinha do artigo)

A análise empírica deve estar **explicitamente mapeada** às normas. Não trate o pipeline de ferramentas como genérico: amarre cada métrica a uma sub-característica.

- **ISO/IEC 25000** — guia "guarda-chuva" da série **SQuaRE** (Software Quality Requirements and Evaluation). Não entrega métricas; organiza a divisão de normas.
- **ISO/IEC 25010** — o **modelo de qualidade** do produto. Na versão **:2011**, possui 8 características, e **Segurança** é uma delas, com 5 sub-características. Na versão **:2023**, foi revisada (9 características) e **Safety foi adicionada como característica própria**; **Segurança** passou a ter uma 6ª sub-característica, **Resistência**. **Importante: o 25010 é um modelo, não um conjunto de métricas prontas.**
- **ISO/IEC 25023** — define as **medidas (métricas)** das características do 25010. **É esta norma que você cita para justificar *como* medir.** Cite 25010 (o modelo) **e** 25023 (as medidas) em conjunto.

> **Ação obrigatória:** confirme as definições e a numeração das versões do 25010 (:2011 vs :2023) diretamente na norma antes de afirmá-las no artigo. Não fabrique sub-características.

### Mapeamento métrica → sub-característica de Segurança (25010)

| Sub-característica (25010) | Como é medida neste estudo | Fonte (sem build) |
| --- | --- | --- |
| **Integridade** | Injeção (CWE-89/78), desserialização insegura (CWE-502), path traversal (CWE-22), XXE (CWE-611) → base do *target* de segurança | **Semgrep / CodeQL (build-mode: none)** |
| **Confidencialidade** | Segredos/credenciais expostos, exposição de informação (CWE-200), criptografia fraca (CWE-327/328) | **Gitleaks + Semgrep** |
| **Autenticidade** | TLS permissivo, autenticação fraca, credenciais fixas | **Semgrep / CodeQL** |
| **Resistência** (:2023) | Exposição via dependências vulneráveis (CVE/CVSS) declaradas nos manifests | **OSV-Scanner** (cobertura transitiva parcial → limitação) |
| **Não-repúdio** e **Responsabilização (accountability)** | **Praticamente não mensuráveis** por SAST/SCA estática → discussão qualitativa / limitação | — |

### Safety (25010:2023)

**Safety trata de prevenção de dano a pessoas/ambiente** (sistemas safety-critical). **Nenhuma das ferramentas deste estudo mede Safety**, e os repositórios da NSA analisados não são safety-critical nesse sentido. Trate Safety de forma **conceitual** na Fundamentação Teórica e declare explicitamente como **limitação** na Conclusão. **Não mapeie achados de SAST para "safety".**

---

## 4. Seleção dos 10 repositórios

### Lista recomendada (verificar antes de fixar)

Priorize sistemas **distintos e substanciais**; evite módulos utilitários/exemplos minúsculos. Lista de partida (existência confirmada na organização; **tamanhos a verificar**):

1. `ghidra` — engenharia reversa; carro-chefe, grande. *(Obs.: tem parcela em C++ no decompilador; a análise considerará apenas a parte Java, o que é correto para o escopo, mas o tamanho "real" é maior que o LOC Java.)*
2. `emissary` — framework distribuído data-driven; maduro.
3. `timely` — banco de série temporal sobre Accumulo.
4. `qonduit` — proxy WebSocket/HTTP para Accumulo.
5. `datawave` — repositório principal do ecossistema DataWave. *(Verificar tamanho atual: pode ter sido esvaziado quando o projeto foi quebrado em microsserviços; se for apenas meta-repo, substituir.)*
6. `fractalrabbit` — simulação de trajetórias; menor, código de pesquisa.
7. `datawave-query-service` — serviço real do DataWave.
8. `datawave-audit-service` — serviço real do DataWave.
9. `datawave-authorization-service` — serviço real do DataWave.
10. `ghidra-lisa` — extensão relacionada ao Ghidra. *(Verificar tamanho; se minúsculo, substituir por outro serviço DataWave substancial.)*

### Critérios e cuidados (descrever na Metodologia)

- **Critério de inclusão:** linguagem principal Java (confirmar no GitHub) e código-fonte real (não documentação/exemplos triviais).
- **Critério de exclusão:** módulos minúsculos do tipo `*-utils`, `*-starter`, `*-examples` e `*-in-memory-*` — eles inflam a contagem para "10", terão **zero achado de segurança** e **quebram o GroupKFold** do ML (fold com classe única).
- **Transparência obrigatória:** declare que **três dos dez** (`datawave-query-service`, `datawave-audit-service`, `datawave-authorization-service`) pertencem ao **mesmo ecossistema DataWave**. Isso afeta a independência das amostras e deve ser citado como variável de controle/confundidora e como limitação de validade externa.
- **Verificação:** liste primeiro os repositórios Java da organização e **meça LOC/contagem de arquivos `.java` reais** (com `cloc` após o clone) antes de fixar a lista final. Descarte os pequenos demais. Registre a lista final e os critérios.

---

## 5. Ferramentas (stack estática, sem build, sem dupla contagem)

| Dimensão | Ferramenta canônica | Papel | Observação crítica |
| --- | --- | --- | --- |
| **Métricas de estrutura/qualidade** | **SonarQube** (Community), em **modo source-only** | Features do ML: complexidade, complexidade cognitiva, duplicação, code smells, tamanho, comentários | **Não é o oráculo de segurança.** Sem bytecode, as regras Java de taint/segurança e parte das de bug **não disparam**; o analisador Java pode exigir flag para rodar sem `sonar.java.binaries` ou avisar análise incompleta — **verificar na sua versão**. As métricas estruturais (AST) funcionam sem build. |
| **SAST de segurança (target)** | **Semgrep** (e/ou **CodeQL `build-mode: none`**) | Detectar vulnerabilidades/fraquezas por arquivo → origem do rótulo `has_security_risk` | 100% código-fonte, sem build. CodeQL em `build-mode: none` extrai Java sem compilar (mais profundo; mais novo). Padronizar a configuração de regras e registrá-la. |
| **Métricas OO (CK)** | **CK (Maurício Aniche)** | Features OO por classe/método: WMC, DIT, NOC, CBO, RFC, LCOM etc. | Só Java; parseia o **fonte** (sem bytecode). Bindings de tipo podem ficar parciais sem classpath → aceitável. |
| **Métricas de processo** | **PyDriller** | Por arquivo: nº de commits que o tocaram, nº de autores, churn, idade, tempo desde a última mudança | Opera sobre o histórico Git; sem build. |
| **SCA (dependências)** | **OSV-Scanner** | CVE + CVSS a partir dos **manifests** (`pom.xml`/Gradle) | Sem build: captura bem **dependências diretas**; **transitivas ficam parciais** → declarar como limitação. **Uma única ferramenta de SCA.** |
| **Segredos** | **Gitleaks** | Credenciais/chaves no estado atual e no histórico | Por arquivo e por 1000 commits; sem build. |
| **Linhas de código** | **cloc** | LOC Java por repositório/arquivo, para normalização | Saída JSON. |
| **Orquestração / análise** | **Python + Pandas + scikit-learn** (+ XGBoost/LightGBM) | Clonar, executar ferramentas estáticas, ler JSON/SARIF/XML, montar dataset, ML, gráficos | — |

**Não empilhe** múltiplas ferramentas redundantes (Trivy + Dependency-Check + Grype + Syft + Scorecard "para ficar completo"): isso amplia a largura ao custo da profundidade num artigo de 6–10 páginas e gera dupla contagem de CVEs. **Opcional**, apenas se for discutir priorização: **EPSS** sobre os CVEs do OSV-Scanner (probabilidade de exploração), distinto do CVSS (severidade técnica).

---

## 5-A. Ferramentas/softwares a instalar (pré-requisitos)

Lista organizada por função, alinhada à abordagem estática (só clone, sem build). Instalar primeiro os runtimes, pois vários analisadores rodam sobre eles.

> **Onde instalar cada coisa (obrigatório) — dois grupos:**
>
> **(1) Dependências do projeto (Python) → DENTRO do projeto, versionadas.** O ambiente virtual (`venv`) com as bibliotecas Python (pandas, scikit-learn, semgrep, pydriller, lizard, xgboost etc.) fica na **pasta do projeto**, descrito por um **`requirements.txt`** versionado no Git. O `venv/` em si **não** é commitado (entra no `.gitignore`); o `requirements.txt`, **sim**. Isso garante reprodutibilidade: clonar o repositório + `pip install -r requirements.txt` recria o ambiente idêntico — atende ao requisito do enunciado de documentar e reproduzir a extração.
>
> **(2) Ferramentas externas (binários pesados, não específicos do projeto) → `E:\developer-tools`.** CodeQL CLI, SonarScanner, servidor SonarQube, `.jar` do CK, binários de OSV-Scanner e Gitleaks (centenas de MB, reaproveitáveis entre projetos) ficam em **`E:\developer-tools`**, cada ferramenta em sua subpasta (ex.: `E:\developer-tools\codeql`, `E:\developer-tools\sonar-scanner`, `E:\developer-tools\ck`), com o `PATH`/variáveis de ambiente apontando para lá. **Não** versione esses binários no Git — manteria o repositório pesado e duplicaria ferramentas a cada projeto.
>
> **Regra que separa os dois:** o que **define o experimento e é leve** vai versionado no projeto (libs Python, configs, scripts, regras do Semgrep); o que é **infraestrutura pesada** fica fora, instalado uma vez (`E:\developer-tools`).
>
> **Reprodutibilidade das ferramentas externas:** como elas ficam fora e não versionadas, **fixe e registre as versões** (ex.: CodeQL x.y, SonarQube 10.z, Semgrep a.b, OSV-Scanner, Gitleaks) num arquivo do projeto (ex.: `TOOLS_VERSIONS.md`), para o estudo seguir reproduzível mesmo com os binários fora do repositório.
>
> **Nota (ambiente Windows):** `E:\developer-tools` é um caminho Windows. Os comandos `apt`/`brew` e o `setup.sh` desta seção são de Linux/macOS e **não se aplicam diretamente** no Windows — use os instaladores nativos, **Chocolatey**/**Scoop** (ex.: `choco install cloc gitleaks`), ou rode tudo via **WSL** (onde o disco aparece como `/mnt/e/developer-tools`).

### Base / runtimes (instalar primeiro)
- **Python 3.9+** — orquestração, montagem do dataset e o Machine Learning. É a espinha.
- **JDK 17 ou 21** (ex.: Temurin/Adoptium) — necessário **mesmo sem buildar** os projetos, porque várias ferramentas rodam na JVM: o **CK**, o **SonarScanner**, a extração Java do **CodeQL** e o **SpotBugs** (se usar).
- **Git** — clonagem dos repositórios e base para o **PyDriller**.
- **Docker** (recomendado) — forma mais simples de subir o servidor SonarQube e de rodar algumas ferramentas isoladas.

### Coleta de segurança (origem do *target* do ML)
- **Semgrep** — `pip install semgrep` (ou `brew install semgrep`). Detector de segurança principal, 100% código-fonte.
- **CodeQL CLI** (opcional, mais profundo) — baixar o bundle em `github.com/github/codeql-cli-binaries`; usar Java em `build-mode: none`.

### Métricas de código / estrutura (features do ML)
Há **dois caminhos**, por causa do impasse do bytecode (ver Seção 9, item 1):
- **Caminho SonarQube** (se aceitar o risco de exigir compilação): **servidor SonarQube** (`docker run -d -p 9000:9000 sonarqube:community`) + **SonarScanner CLI** (site da SonarSource, ou `npm i -g sonarqube-scanner`).
- **Caminho nativo de fonte** (mais coerente com "sem build"; roda sem compilar nada): **cloc** (`apt`/`brew install cloc`) para tamanho/LOC + **lizard** (`pip install lizard`) para complexidade ciclomática e cognitiva.
- **CK (Maurício Aniche)** — em **qualquer** caminho, para métricas OO (WMC, DIT, CBO, RFC, LCOM). Clonar `github.com/mauricioaniche/ck`, rodar `mvn clean package` e usar o `.jar` gerado (`java -jar ck.jar`).

### Dependências e segredos
- **OSV-Scanner** — `brew install osv-scanner` ou binário de release (lê os manifests `pom.xml`/Gradle, sem build).
- **Gitleaks** — `brew install gitleaks` ou binário de release (segredos no código atual e no histórico).

### Métricas de processo
- **PyDriller** — `pip install pydriller`. **Atenção:** precisa do **clone completo** (não use `--depth 1` nesta etapa, ao contrário do SonarQube).

### Machine Learning e análise (bibliotecas Python)
- `pip install pandas scikit-learn numpy matplotlib seaborn xgboost lightgbm imbalanced-learn shap` — `imbalanced-learn` para o SMOTE; `shap` (opcional) para interpretar a importância das features.

### Conjunto mínimo viável
**Python + JDK + Git + Semgrep + cloc + lizard + CK + OSV-Scanner + Gitleaks + PyDriller + libs de ML.** Docker e SonarQube entram **só** se optar pelo caminho SonarQube; CodeQL é reforço **opcional** do target.

---

## 6. Métricas a extrair

Extrair de forma **automatizada** (requisito do enunciado), tudo por análise estática. Para o SonarQube, usar a **Web API** (`/api/measures/component`) — nunca copiar números do dashboard à mão.

### 6.1 Segurança (target) — Semgrep / CodeQL
Achados de segurança por arquivo, com severidade e CWE/OWASP quando disponíveis. **Esta é a fonte do rótulo do ML** (Seção 8), porque, sem build, o SonarQube não detecta segurança Java de forma confiável. Coletar o mapeamento para **CWE / OWASP Top 10 / CWE Top 25** para a discussão qualitativa.

### 6.2 SonarQube — Estrutura, Manutenibilidade, Tamanho, Complexidade, Duplicação (features)
`ncloc`, `lines`, `files`, `classes`, `functions`, `comment_lines`, `comment_lines_density`; `complexity`, `cognitive_complexity`; `duplicated_lines`, `duplicated_lines_density`, `duplicated_blocks`; `code_smells`, `sqale_index`, `sqale_debt_ratio`, `sqale_rating`; `violations`, `blocker_violations`, `critical_violations`, `major_violations`, `minor_violations`.
> **Cuidado (source-only):** métricas de tamanho/complexidade/duplicação/comentários são confiáveis sem build. **Code smells e issues** vêm **majoritariamente** — regras que dependem de semântica/bytecode não disparam; registre essa limitação. Métricas de **Confiabilidade** (`bugs`, `reliability_rating`) ficam **parciais** sem bytecode → use com ressalva ou trate como secundárias.
> **Atenção à versão:** SonarQube 10.x+ usa a taxonomia **Clean Code / modo MQR** (impacto Alto/Médio/Baixo por categoria). Verifique a versão e registre o modo usado.

### 6.3 Cobertura — fora do escopo
`coverage`/`line_coverage`/`branch_coverage`/`uncovered_lines` **exigem executar a suíte de testes**, o que **não será feito** (regra 2). Portanto, **cobertura não entra no dataset**; declare explicitamente como limitação no artigo.

### 6.4 CK (métricas OO, por classe)
WMC, DIT, NOC, CBO, RFC, LCOM, LCOM*, número de métodos/atributos, acoplamentos aferente/eferente etc. Agregar ao nível de arquivo quando o arquivo tiver mais de uma classe.

### 6.5 PyDriller (métricas de processo, por arquivo)
nº de commits que modificaram o arquivo, nº de autores distintos, churn (linhas adicionadas/removidas), idade do arquivo, tempo desde a última modificação.

### 6.6 SCA e Segredos (nível de repositório, para estatística descritiva)
CVEs totais e por severidade (diretas; transitivas parciais → limitação), CVSS médio; segredos no estado atual e no histórico, por tipo.

### 6.7 Normalização
Sempre reportar valores **brutos e normalizados por KLOC** para permitir comparação justa entre projetos de tamanhos muito diferentes (ex.: Ghidra vs. fractalrabbit). Ex.: `achados_seguranca_por_kloc = achados / (ncloc/1000)`.

---

## 7. Construção do dataset (nível de arquivo `.java`)

A unidade de análise é o **arquivo `.java`** (não o repositório — 10 repositórios dariam apenas 10 amostras). 10 repositórios Java grandes geram milhares de arquivos, suficiente para ML.

Para cada arquivo, consolidar em uma linha: identificação (`repo`, `file_path`), métricas estruturais do SonarQube, métricas CK agregadas, métricas de processo (PyDriller) e o **rótulo de segurança** (Semgrep/CodeQL). Persistir como CSV versionado, com dicionário de dados documentando cada coluna e sua origem/norma.

---

## 8. Machine Learning

### 8.1 Problema e target
Classificação binária por arquivo, com rótulo derivado do **SAST de segurança (Semgrep/CodeQL)**:
```
has_security_risk = 1  se o arquivo possui >= 1 achado de segurança (Semgrep/CodeQL)
has_security_risk = 0  caso contrário
```
*(Documentar a configuração de regras usada e a limitação de qualidade do rótulo — ver Seção 9. Opcionalmente, refinar para classes de severidade baixo/médio/alto.)*

### 8.2 EVITAR VAZAMENTO DE DADOS (crítico)
O *target* vem do SAST de segurança; portanto **nenhuma contagem/severidade de achados de segurança pode ser feature** (Semgrep/CodeQL, ou métricas de segurança do SonarQube). Usá-las como entrada seria circular. As features vêm de **estrutura/qualidade (SonarQube), OO (CK) e processo (PyDriller)** — dimensões distintas da que origina o rótulo.

### 8.3 Features permitidas
`ncloc`, `complexity`, `cognitive_complexity`, `code_smells`, `duplicated_lines_density`, `comment_lines_density`, `functions`, `classes`, `violations` e severidades **não relacionadas a segurança** (`blocker/critical/major/minor`), **métricas CK** e **métricas de processo (PyDriller)**. *(Sem cobertura — Seção 6.3. `bugs`/`reliability` só se considerados confiáveis no seu setup source-only.)*

### 8.4 Desbalanceamento (crítico)
Arquivos com risco de segurança são **raros** → **accuracy engana**. Liderar a avaliação por **Precision, Recall, F1-Score, ROC-AUC e Matriz de Confusão**; priorizar **Recall e F1** (em segurança, deixar passar arquivo arriscado é o pior erro). Tratar desbalanceamento com `class_weight="balanced"` e/ou SMOTE; manter split estratificado.

### 8.5 Validação
**GroupKFold agrupado por repositório** (treina em N−1 repos, testa no restante), para medir generalização entre projetos e evitar otimismo por similaridade intra-repositório.
> **Cuidado obrigatório:** um fold de teste composto por repositório com **classe única** (só negativos) faz `roc_auc` falhar ("Only one class present") e deixa precision/recall indefinidos. **Por isso os repositórios minúsculos da Seção 4 devem ser excluídos.** Garanta que cada fold de teste contenha ambas as classes; trate exceções de forma robusta.

### 8.6 Modelos
Comparar, no mínimo: **Regressão Logística** (baseline interpretável), **Árvore de Decisão** (interpretável para a apresentação), **Random Forest** (modelo principal, robusto em dados tabulares) e **XGBoost** e/ou **LightGBM** (avançado). Para LogReg/SVM/KNN, padronizar as features.

### 8.7 Importância de features → ligação com a ISO
Reportar a **importância das variáveis** do Random Forest (e, se possível, SHAP). Este é o resultado que sustenta o argumento central: **quais métricas de qualidade mais predizem proneness a risco de segurança** — alimentando diretamente a discussão sobre a relação entre características do 25010.

---

## 9. Riscos e armadilhas a tratar EXPLICITAMENTE

1. **Sem build → SonarQube não é oráculo de segurança Java.** As regras de taint/segurança e parte das de bug exigem bytecode; sem ele, `vulnerabilities` vem quase vazio (e o analisador Java pode exigir flag para rodar sem `sonar.java.binaries`). **Por isso o target vem de Semgrep/CodeQL.** Use o SonarQube apenas para métricas estruturais. Discuta essa decisão no artigo.
2. **Qualidade do rótulo (source-only SAST).** Semgrep/CodeQL em código-fonte podem gerar falsos positivos/negativos; o rótulo `has_security_risk` é uma **aproximação**. Registre a configuração de regras e discuta como limitação.
3. **Piloto obrigatório.** Antes do pipeline inteiro, rode Semgrep (e/ou CodeQL) em **1–2 repositórios** e **conte quantos arquivos `.java` recebem algum achado de segurança**. Se a base de positivos for ínfima, ajuste o conjunto de regras (ex.: rulesets de segurança Java) ou adote CodeQL antes de escalar.
4. **SCA limitada a manifests.** Sem build, dependências **transitivas** podem não ser resolvidas; a SCA captura sobretudo as **diretas** → declarar como limitação.
5. **Cobertura ausente** (não há execução de testes) → limitação (Seção 6.3).
6. **Homogeneidade do DataWave** → limitação de validade externa (Seção 4).
7. **Referências e fatos verificáveis.** Maior risco de qualquer LLM ao escrever artigo é **citação fabricada**. **Confira cada referência** (DOI, arXiv, autores) antes de incluí-la no Overleaf; não afirme número total de repositórios da organização nem nomes de repositório sem verificar.
8. **Reprodutibilidade.** Dependências Python no projeto via **`requirements.txt`** versionado (`venv/` no `.gitignore`); ferramentas externas pesadas em **`E:\developer-tools`**, com **versões fixadas e registradas** (ex.: `TOOLS_VERSIONS.md`) já que não são versionadas no Git (ver Seção 5-A). Registre também o conjunto de regras do SAST; publique dataset + scripts (o enunciado pede documentar a extração).

---

## 10. Entregáveis

1. **Scripts de coleta automatizada** (Python): clone, execução das ferramentas **estáticas**, leitura de JSON/SARIF/XML, montagem do dataset. Código organizado e documentado. **Sem etapas de build/execução dos projetos.**
2. **Dataset** em CSV (nível de arquivo) + **dicionário de dados** mapeando cada coluna à sua origem e, quando aplicável, à sub-característica do 25010.
3. **Relatórios de resultados:** estatística descritiva comparativa dos 10 repositórios (postura de segurança mapeada às sub-características do 25010, valores brutos e por KLOC); tabela comparativa de algoritmos; matriz de confusão; curva/valor ROC-AUC; ranking de importância de features. Gráficos prontos para o artigo.
4. **Artigo científico (padrão SBC, 6–10 páginas, Overleaf)** com a estrutura abaixo. **Usar o template oficial da SBC** (não IEEE/ACM).

### Estrutura do artigo

1. **Introdução** — contexto, problema, pergunta de pesquisa, contribuições.
2. **Fundamentação Teórica** — SQuaRE/ISO 25000; ISO 25010 com foco em **Segurança** (sub-características) e menção a **Safety**; **ISO 25023** como base das medidas; conceitos de SAST e SCA; noções de ML; **trabalhos relacionados** de predição de defeitos/vulnerabilidades.
3. **Metodologia** — critérios de seleção dos 10 repositórios (com a transparência DataWave); **abordagem estática (apenas clone, sem build)**; pipeline de extração (Semgrep/CodeQL para o target; SonarQube para métricas estruturais; CK; PyDriller; OSV-Scanner; Gitleaks); descrição do dataset; pré-processamento; engenharia de atributos; tratamento de vazamento e de desbalanceamento; split (GroupKFold); algoritmos; métricas de avaliação.
4. **Resultados e Discussão** — postura de segurança dos repositórios mapeada às sub-características do 25010; comparação dos modelos; matriz de confusão; ROC-AUC; **importância das features** e sua leitura à luz do 25010 (relação Manutenibilidade/Confiabilidade → Segurança).
5. **Conclusão** — síntese; **limitações** (Safety não medido; cobertura ausente; SCA transitiva parcial; rótulo de segurança aproximado por SAST estático; SonarQube sem bytecode; homogeneidade DataWave); trabalhos futuros.
6. **Referências** — todas verificadas.

---

## 11. Critérios de aceitação (a tarefa só está pronta se)

- [ ] Os repositórios foram **apenas clonados**; **nenhum projeto foi buildado, compilado ou executado**.
- [ ] **Antes de qualquer ação, a estrutura e a linguagem de cada repositório foram inspecionadas e compreendidas.**
- [ ] Os 10 repositórios são Java-primários, verificados, e a homogeneidade DataWave está declarada.
- [ ] O **target** de segurança vem de SAST nativo de fonte (**Semgrep/CodeQL**), não do SonarQube; o SonarQube é usado só para métricas estruturais.
- [ ] Nenhuma feature do ML deriva do target (sem vazamento).
- [ ] A avaliação lidera por Precision/Recall/F1/ROC-AUC (não accuracy), com desbalanceamento tratado.
- [ ] Validação por GroupKFold sem folds de classe única.
- [ ] Cada métrica de segurança está mapeada a uma sub-característica do 25010, com 25023 citada para as medidas.
- [ ] Safety e não-repúdio/responsabilização aparecem como discussão qualitativa/limitação, não como medição.
- [ ] Piloto realizado antes do pipeline completo; conjunto de regras do SAST registrado.
- [ ] Limitações do modo estático declaradas (cobertura ausente, SCA transitiva parcial, rótulo aproximado).
- [ ] Processo de extração documentado e reprodutível (versões e regras fixadas).
- [ ] O código dos repositórios sob análise não foi modificado; qualquer configuração de análise é isolada e documentada.
- [ ] Todas as referências verificadas; nenhum fato verificável afirmado sem verificação.
