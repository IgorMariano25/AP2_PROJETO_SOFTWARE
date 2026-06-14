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

| Ferramenta | Versão | Origem | Observação |
|---|---|---|---|
| CK (Maurício Aniche) | 0.7.0 | Maven Central `ck-0.7.0-jar-with-dependencies.jar` (fat-jar) → `tools/ck.jar` | última versão publicada; standalone, sem build |
| OSV | API `https://api.osv.dev/v1/query` (sem binário) | api.osv.dev | consultada via Python (`collect_osv_metrics.py`) |

## Parâmetros de execução fixados

- **Semgrep (alvo):** `--config auto`. Regras `p/java` retornaram 0 achados no piloto;
  `auto` dispara regras `java.lang.security.audit.*` com tags CWE. Achado por arquivo
  `.java` → `has_security_risk = 1`.
- **CK:** `java -jar ck.jar <raiz> false 0 true <prefixo_saida>/` (sem variáveis de tipo
  por classpath → bindings parciais, aceitável). Para `ghidra`, execução **particionada por
  módulo** (`**/src/main/java`, `**/src/test/java`) para isolar o NPE do JDT em um único
  módulo (ver `collect_ck_ghidra.py` e RUN_LOG D5).
- **PyDriller:** clone **completo** (sem `--depth 1`); métricas por arquivo `.java`.
- **OSV:** lê manifests `pom.xml`/Gradle (dependências **diretas** confiáveis;
  **transitivas parciais** sem build → limitação declarada).
- **detect-secrets:** scan do estado atual; resultado descritivo (não é feature do ML).

## Substituições documentadas em relação ao prompt

| Prompt (canônico) | Usado neste estudo | Motivo |
|---|---|---|
| SonarQube (métricas estruturais) | lizard + javalang (nativos de fonte) | mais coerente com "só clone, sem build"; SonarQube exigiria bytecode |
| Gitleaks (binário) | detect-secrets (Python) | evita instalar binário; mesma dimensão (Confidencialidade) |
| CodeQL (opcional) | não utilizado | Semgrep já fornece o alvo; CodeQL era reforço opcional |
</content>
</invoke>
