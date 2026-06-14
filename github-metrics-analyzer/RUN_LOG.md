# RUN_LOG — Sessão noturna autônoma (AP2 Segurança NSA Java)

Log append-only. Cada entrada: timestamp, ação/comando, resultado. Linhas
`DECISÃO:` marcam escolhas feitas autonomamente (sem aprovação do usuário),
sempre com a justificativa ("porque ...").

Regras seguidas (do prompt do usuário):
- Apenas clonar; não buildar/executar projetos.
- Não modificar o código sob análise (só scripts/configs da coleta).
- NUNCA inventar/estimar/preencher métrica. Métrica não coletável → ausente/nula + motivo aqui.
- Em bloqueio: registrar, pular o item, continuar os demais. Não travar o pipeline inteiro.
- Manter desenho metodológico (target via Semgrep; features estruturais; GroupKFold por repo).
- Resultados parciais por repositório (retomável).

Fuso: horário local da máquina. Data de início: 2026-06-08 ~23:53 → 2026-06-09.

---

## Estado inicial encontrado
- 10 repos NSA já clonados em `repos/` (fonte: `repos.txt`).
- Concluídos antes desta sessão: `loc.csv` (10/10), `osv_summary.csv`/`osv_findings.csv` (10/10).
- INCOMPLETOS/STALE detectados nesta sessão (ver D6):
  - `complexity.csv`: só 2/10 repos (emissary, ghidra).
  - `structure.csv`: 0/10 NSA — continha repos LEGADO (alibaba_nacos, elasticsearch, ...).
  - `pydriller_metrics.csv`: só 4/10 repos.

---

## Linha do tempo

**23:5x — DECISÃO D1:** Sincronizei `run_sonarqube_nsa.py` `REPOS` com `repos.txt`/`loc.csv`
(removi `qonduit` e `ghidra-lisa`; adicionei `lemongrenade` e `rank-based-linkage`),
*porque* o `REPOS` do script estava dessincronizado dos 10 repos reais do dataset.

**23:53 — Semgrep (target):** iniciado em background sobre os 10 repos.
→ CONCLUÍDO 00:32. 498 findings; 10/10 repos com achados; **229 arquivos .java positivos** (target).

**23:56 — CK + detect-secrets:** iniciados em background (concorrentes com Semgrep).

**23:56 — DECISÃO D2 (CK jar):** download falhou (404) na URL de release do GitHub
`v0.7.1/...jar-with-dependencies.jar` (esse release não existe). Consultei a API de releases
(sem assets) e o Maven Central. *Decisão:* usar o fat-jar oficial do Maven Central
`com.github.mauricioaniche:ck:0.7.0` (`ck-0.7.0-jar-with-dependencies.jar`, 16 MB) e corrigir
`CK_DOWNLOAD_URL` em `collect_ck_metrics.py`, *porque* 0.7.0 é a última versão publicada e o
fat-jar é executável standalone (sem build).

**00:01 — DECISÃO D3 (CK path no Windows):** CK falhou em todos os repos com
`FileNotFoundException ...repo"class.csv`. Causa: o arg de saída era `"{tmp}{os.sep}"` →
`"...\dir\"`, e a barra invertida final escapa a aspa de fechamento no Windows, corrompendo o
caminho. *Decisão:* passar todos os caminhos com barra normal (`as_posix()`) e prefixo de saída
terminando em `/`, *porque* o Java aceita `/` no Windows e evita o bug de aspas. (Não altera métrica.)

**00:13 — DECISÃO D4 (CK colunas):** o `class.csv` do CK 0.7.0 usa `totalMethodsQty`,
`staticMethodsQty`, `totalFieldsQty`, `staticFieldsQty` — mas a agregação lia
`totalMethodsIncludingGettersSetters`/`staticMethods`/`totalFields`/`staticFields` (inexistentes →
sempre 0). *Decisão:* corrigir os nomes para os do CK 0.7.0 (verificados no header gerado),
*porque* sem isso num_methods/num_fields sairiam zerados (dado errado).

**00:15 — CK re-executado:** CONCLUÍDO 00:21. **9/10 repos OK** (5530 linhas).
→ **ghidra FALHOU** (ver D5).

**00:20 — detect-secrets:** CONCLUÍDO. 251 ocorrências; `secrets_summary.csv` (10/10 repos).
(Não entra como feature do ML — é descritiva/Confidencialidade.)

**00:20 — FALHA ghidra no CK / DECISÃO D5:** CK 0.7.0 abortou ghidra em ~18s com
`java.lang.NullPointerException: ...TypeBinding.kind() because "receiverType" is null`
(bug conhecido do JDT no CK sem classpath). Um único arquivo não-resolvível derruba a run inteira
do repo → 0 registros para ghidra (15.589 .java). *Decisão:* coletar CK do ghidra **particionando
por módulo** (93 `src/main/java` + 52 `src/test/java` = 145 raízes), rodando CK por raiz, de modo
que um arquivo problemático perca só o módulo dele; agregar e anexar ghidra ao `ck_metrics.csv`.
Módulos que ainda assim falharem serão registrados como ausentes (sem fabricar valores).

**00:33 — DECISÃO D6 (re-coleta nativa retomável):** `complexity`/`structure`/`pydriller`
acumulam tudo em memória e só gravam o CSV no fim (não retomável; sobrescrevem). Estado atual
incompleto/stale (ver "Estado inicial"). *Decisão:* criar `collect_native_resumable.py` que
reutiliza as MESMAS funções de análise (sem mudar métrica), salva **1 CSV parcial por repo**
imediatamente, **pula repos já feitos** e **regenera `structure.csv`** do zero para os 10 NSA
(o atual é legado), *porque* atende à exigência de retomabilidade/parciais e à integridade dos dados.
Semeio os parciais com os dados NSA válidos já existentes (complexity: emissary+ghidra;
pydriller: 4 repos) para não recomputar à toa.

`10:32:56` [ck-ghidra] iniciando CK particionado em ghidra: 145 raizes de modulo.
`10:32:59` [native] complexity: semeado de dados existentes — NationalSecurityAgency/emissary (6079 linhas).
`10:33:00` [native] complexity: semeado de dados existentes — NationalSecurityAgency/ghidra (173635 linhas).
`10:33:00` [native] complexity: iniciando — 10 repos (menor->maior).
`10:33:00` [native] complexity: NationalSecurityAgency/fractalrabbit 10:33:00->10:33:00 — 72 linhas (ok).
`10:33:00` [native] complexity: NationalSecurityAgency/rank-based-linkage 10:33:00->10:33:00 — 131 linhas (ok).
`10:33:00` [native] complexity: NationalSecurityAgency/datawave-authorization-service 10:33:00->10:33:00 — 338 linhas (ok).
`10:33:01` [native] complexity: NationalSecurityAgency/datawave-audit-service 10:33:00->10:33:01 — 554 linhas (ok).
`10:33:02` [native] complexity: NationalSecurityAgency/lemongrenade 10:33:01->10:33:02 — 1093 linhas (ok).
`10:33:03` [native] complexity: NationalSecurityAgency/datawave-query-service 10:33:02->10:33:03 — 746 linhas (ok).
`10:33:05` [native] complexity: NationalSecurityAgency/timely 10:33:03->10:33:05 — 2427 linhas (ok).
`10:34:45` [native] complexity: NationalSecurityAgency/datawave 10:33:05->10:34:45 — 48746 linhas (ok).
`10:34:54` [native] complexity: MERGE -> complexity.csv (233821 linhas, 10 repos).
`10:34:54` [native] structure: iniciando — 10 repos (menor->maior).
`10:34:55` [native] structure: NationalSecurityAgency/fractalrabbit 10:34:54->10:34:55 — 25 linhas (ok).
`10:34:56` [native] structure: NationalSecurityAgency/rank-based-linkage 10:34:55->10:34:56 — 23 linhas (ok).
`10:34:57` [native] structure: NationalSecurityAgency/datawave-authorization-service 10:34:56->10:34:57 — 68 linhas (ok).
`10:35:02` [native] structure: NationalSecurityAgency/datawave-audit-service 10:34:57->10:35:02 — 79 linhas (ok).
`10:35:08` [native] structure: NationalSecurityAgency/lemongrenade 10:35:02->10:35:08 — 119 linhas (ok).
`10:35:15` [native] structure: NationalSecurityAgency/datawave-query-service 10:35:08->10:35:15 — 69 linhas (ok).
`10:35:30` [native] structure: NationalSecurityAgency/timely 10:35:15->10:35:30 — 407 linhas (ok).
`10:36:02` [native] structure: NationalSecurityAgency/emissary 10:35:30->10:36:02 — 803 linhas (ok).
`18:01:35` [native] pydriller: semeado de dados existentes — NationalSecurityAgency/datawave (2968 linhas).
`18:01:35` [native] pydriller: semeado de dados existentes — NationalSecurityAgency/datawave-authorization-service (64 linhas).
`18:01:35` [native] pydriller: semeado de dados existentes — NationalSecurityAgency/datawave-query-service (54 linhas).
`18:01:35` [native] pydriller: semeado de dados existentes — NationalSecurityAgency/emissary (690 linhas).
`18:01:35` [native] pydriller: iniciando — 10 repos (menor->maior).
`18:01:37` [ck-ghidra] iniciando CK particionado em ghidra: 145 raizes de modulo.
`18:01:42` [native] pydriller: NationalSecurityAgency/fractalrabbit 18:01:35->18:01:42 — 49 linhas (ok).
`18:01:43` [native] pydriller: NationalSecurityAgency/rank-based-linkage 18:01:42->18:01:43 — 34 linhas (ok).
`18:02:11` [native] pydriller: NationalSecurityAgency/datawave-audit-service 18:01:43->18:02:11 — 63 linhas (ok).
`18:02:15` [native] pydriller: NationalSecurityAgency/lemongrenade 18:02:11->18:02:15 — 126 linhas (ok).
`18:03:56` [native] pydriller: NationalSecurityAgency/timely 18:02:15->18:03:56 — 724 linhas (ok).
`18:17:20` [ck-ghidra] CK ghidra concluido: 13416 arquivos; 0/145 raizes falharam no CK (registradas como ausentes, nao fabricadas). ck_metrics.csv agora com 10 repos.
`18:27:34` [native] pydriller: NationalSecurityAgency/ghidra 18:03:56->18:27:34 — 22337 linhas (ok).
`18:27:34` [native] pydriller: MERGE -> pydriller_metrics.csv (27109 linhas, 10 repos).