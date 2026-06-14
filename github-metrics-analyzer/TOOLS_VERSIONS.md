# TOOLS_VERSIONS — Versões e parâmetros das ferramentas

Registro de reprodutibilidade exigido pelo enunciado (§5-A e §9.8 do prompt).
Fixa as versões das ferramentas e os parâmetros de execução usados na coleta.
Ferramentas externas pesadas não são versionadas no Git; as versões ficam aqui.

- **Data da coleta:** 2026-06-08/09 (Semgrep, OSV, detect-secrets, LOC, complexidade,
  estrutura, CK exceto ghidra) e 2026-06-13 (CK ghidra particionado + PyDriller 10/10).
- **Plataforma:** Windows 11 Pro (10.0.26200), PowerShell.
- **Modo de análise:** estático, sobre o código-fonte clonado. **Nenhum projeto foi
  buildado, compilado ou executado.**

## Runtimes

| Componente | Versão |
|---|---|
| Python | 3.12.0 |
| JDK (para o CK) | OpenJDK 24.0.2 (2025-07-15) |
| Git | 2.54.0.windows.1 |
| cloc | ausente no PATH → **fallback contador em Python** (ver `collect_loc_metrics.py`) |

## Dependências Python (do `requirements.txt`, no `venv` do projeto)

| Pacote | Versão | Papel |
|---|---|---|
| semgrep | 1.165.0 | SAST — alvo do ML |
| pydriller | 2.9 | métricas de processo (feature) |
| lizard | 1.22.2 | complexidade ciclomática (feature) |
| javalang | 0.13.0 | estrutura/OO (feature) |
| detect-secrets | 1.5.0 | segredos (descritivo) |
| pandas | 3.0.3 | montagem do dataset |
| numpy | 2.4.6 | numérico |
| scikit-learn | 1.9.0 | ML (modelos, GroupKFold, métricas) |
| xgboost | 3.2.0 | ML (modelo avançado) |
| lightgbm | 4.6.0 | ML (modelo avançado) |
| imbalanced-learn | 0.14.2 | SMOTE (desbalanceamento) |
| shap | 0.52.0 | interpretabilidade de features |
| matplotlib | 3.10.9 | gráficos |
| seaborn | 0.13.2 | gráficos |

## Ferramentas externas (fora do Git)

Instaladas na pasta `developer-tools/` dentro do projeto (uma por subpasta,
gitignored) pelo instalador idempotente `scripts/setup_dev_tools.ps1`. Não
versionadas no Git; runtimes do SO (Java/Git/Docker) e o `venv` Python ficam
fora desta tabela.

| Ferramenta | Versão | Local / origem | Observação |
|---|---|---|---|
| CK (Maurício Aniche) | 0.7.0 | `developer-tools/ck/ck.jar` (Maven Central, fat-jar) | migrado de `tools/ck.jar`; standalone, sem build |
| OSV | API `https://api.osv.dev/v1/query` (sem binário) | api.osv.dev | consultada via Python (`collect_osv_metrics.py`) |
| Gitleaks | 8.30.1 | `developer-tools/gitleaks/gitleaks.exe` (release GitHub) | scan do estado atual (`gitleaks dir`) |
| SonarScanner CLI | 6.2.1.4610 | `developer-tools/sonar-scanner/bin/sonar-scanner.bat` | `-Dsonar.java.binaries=<fontes>` (sem bytecode) |
| CodeQL (bundle) | 2.25.6 (`codeql-bundle-v2.25.6`) | `developer-tools/codeql/codeql.exe` (github/codeql-action) | inclui query packs; `--build-mode=none`; suíte `java-security-extended` |
| SonarQube (servidor) | 26.6.0.123539 (Community Build) | imagem Docker `sonarqube:community` | métricas estruturais (source-only); modo MQR/Clean Code (padrão na 26.x); **exige User Token** (não Global Analysis Token) para leitura via Web API |

> **Servidor SonarQube** não fica em pasta: roda via Docker
> (`docker run -d -p 9000:9000 sonarqube:community`, ou
> `setup_dev_tools.ps1 -PullSonarQubeImage`). Após subir, preencha a versão
> acima e gere o token (`SONAR_TOKEN`).

## Parâmetros de execução fixados

- **Alvo de segurança (Semgrep ∪ CodeQL):** `has_security_risk = 1` se o arquivo `.java`
  for sinalizado por **qualquer** das duas SASTs (união → maximiza recall). Contagens
  por ferramenta (`n_semgrep`, `n_codeql`) ficam no dataset só para concordância e são
  **excluídas das features** do ML (anti-vazamento).
- **Semgrep:** `--config auto` (dispara `java.lang.security.audit.*` com tags CWE;
  `p/java` retornou 0 no piloto).
- **CodeQL:** `database create --build-mode=none` + `analyze java-security-extended.qls`
  (SARIF v2.1.0). Sem compilar o projeto.
- **SonarQube (estrutural canônico):** scanner source-only (`sonar.java.binaries`
  apontado para os fontes); métricas lidas pela Web API `/api/measures/component_tree`
  (`qualifiers=FIL`), nunca do dashboard. Regras de segurança/bug que exigem bytecode
  **não disparam** (§9.1) → usado só para estrutura. lizard fica como fallback offline.
- **CK:** `java -jar ck.jar <raiz> false 0 true <prefixo_saida>/` (sem variáveis de tipo
  por classpath → bindings parciais, aceitável). Para `ghidra`, execução **particionada por
  módulo** (`**/src/main/java`, `**/src/test/java`) para isolar o NPE do JDT em um único
  módulo (ver `collect_ck_ghidra.py` e RUN_LOG D5).
- **PyDriller:** clone **completo** (sem `--depth 1`); métricas por arquivo `.java`.
- **OSV:** lê manifests `pom.xml`/Gradle (dependências **diretas** confiáveis;
  **transitivas parciais** sem build → limitação declarada).
- **Segredos (Gitleaks + detect-secrets):** scan do estado atual pelas duas ferramentas,
  **união deduplicada** por (arquivo, linha, tipo), com coluna `detected_by`
  (gitleaks/detect-secrets/both) para validação cruzada. Descritivo — não é feature/alvo
  do ML, então combinar não causa vazamento nem dupla contagem.

## Alinhamento com o prompt (stack canônica completa)

A stack agora segue as ferramentas canônicas do prompt (§5). Ferramentas com
dependência pesada degradam com elegância quando ausentes (ver README).

| Prompt (canônico) | Implementação | Observação |
|---|---|---|
| SonarQube (métricas estruturais) | **SonarQube** (canônico) + lizard (fallback) | source-only; lizard só quando o servidor não está disponível |
| Semgrep / CodeQL (alvo) | **Semgrep ∪ CodeQL** (união) | CodeQL `build-mode none`; alvo = OR das duas |
| Gitleaks (segredos) | **Gitleaks** + detect-secrets (união deduplicada) | validação cruzada na mesma dimensão |
| CK / PyDriller / OSV | inalterado | OO / processo / SCA |

> A versão anterior usava lizard+javalang (estrutura), só Semgrep (alvo) e só
> detect-secrets (segredos). O javalang foi removido (redundante com o CK).
</content>
</invoke>
