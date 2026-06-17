# Prompt para gerar os slides no Claude.ai

> **Como usar:** copie todo o conteúdo abaixo da linha `=== INÍCIO DO PROMPT ===`
> e cole no Claude.ai. O prompt é **autossuficiente** — todos os dados reais do
> projeto já estão embutidos, então o Claude consegue montar a apresentação sem
> acessar o repositório. Se quiser slides como artefato visual, peça ao final
> "gere como artefato HTML/React" (o prompt já pede isso).

---

=== INÍCIO DO PROMPT ===

Você é um **designer de apresentações acadêmicas** especializado em comunicar
projetos técnicos de Engenharia de Software para bancas. Preciso que você crie
uma **apresentação de slides** sobre o meu projeto de pesquisa.

## Contexto da apresentação

- **Público:** o coordenador do meu curso de Engenharia de Software e professores
  convidados (público técnico, mas nem todos especialistas em Machine Learning).
- **Objetivo:** explicar, do início ao fim, o que o projeto faz, como funciona o
  pipeline, e a parte de Machine Learning (treino, validação, métricas e
  resultados).
- **Tom:** profissional, didático e visual. Cada slide deve ter pouco texto
  (tópicos curtos, não parágrafos), com o detalhamento ficando para a minha fala.
- **Idioma:** Português do Brasil.
- **Duração estimada:** 12 a 15 minutos (≈ 14 a 18 slides).

## Formato de saída que eu quero

1. Primeiro, entregue a apresentação como **artefato em HTML/React** (slides
   navegáveis, um conceito por slide, visual limpo, paleta sóbria — azul/cinza —
   com bom uso de ícones, tabelas e diagramas simples).
2. Para **cada slide**, inclua nas *notas do apresentador* (campo separado, não
   no slide visível) um **roteiro de fala** de 3 a 5 frases que eu vou narrar.
3. Use diagramas/ASCII ou caixas para representar o fluxo do pipeline e o esquema
   de validação por repositório.

## Sobre o projeto (use estes dados reais — não invente números)

**Nome:** GitHub Metrics Analyzer (AP2)

**Resumo em uma frase:** pipeline estática, automatizada e reprodutível de
Mineração de Repositórios de Software (MSR) que coleta métricas de qualidade e
segurança de **10 repositórios Java da NationalSecurityAgency (NSA)** no GitHub,
monta um dataset em nível de arquivo e treina modelos de Machine Learning para
**prever quais arquivos `.java` são propensos a risco de segurança**, ancorando
tudo na norma **ISO/IEC 25010**.

**Princípio central:** análise **100% estática** — nenhum projeto é compilado,
*buildado* ou executado. Só se analisa o código-fonte clonado.

### Ferramentas de análise usadas
- **Semgrep** e **CodeQL** (SAST) → definem o **alvo** de segurança (união).
- **SonarQube** (servidor via Docker + SonarScanner) → métricas estruturais
  canônicas (complexidade, complexidade cognitiva, duplicação, code smells,
  dívida técnica).
- **lizard** → complexidade ciclomática (fallback estrutural offline).
- **CK** (Maurício Aniche) → métricas de orientação a objetos (WMC, DIT, CBO,
  RFC, LCOM, TCC…).
- **PyDriller** → métricas de processo do histórico git (commits, autores,
  churn, idade do arquivo).
- **OSV** (API) → CVEs em dependências declaradas (descritivo).
- **Gitleaks + detect-secrets** → detecção de segredos (descritivo).

### Fluxo do pipeline (orquestrado por `run_all.py`, nesta ordem)
1. **clone** → clona os 10 repositórios NSA (sem build) em `repos/`.
2. **loc** → `loc.csv` (linhas de código, normalização KLOC).
3. **complexity** → `complexity.csv` (lizard, por método).
4. **sonarqube** → `sonarqube.csv` (estrutural canônico, por arquivo).
5. **semgrep** → `semgrep_findings.csv` (alvo SAST #1).
6. **codeql** → `codeql_findings.csv` (alvo SAST #2; união com Semgrep).
7. **pydriller** → `pydriller_metrics.csv` (processo, feature).
8. **ck** → `ck_metrics.csv` (OO, feature).
9. **osv** → `osv_findings.csv` + `osv_summary.csv` (descritivo).
10. **secrets** → `secrets_findings.csv` + `secrets_summary.csv` (descritivo).
11. **dataset** → junta TODOS os CSVs em `security_dataset.csv` (1 linha por
    arquivo `.java`) — é uma **barreira de agregação**.
12. **ml** → lê só o `security_dataset.csv`, treina e avalia os modelos.
13. **report** → relatório comparativo ISO 25010 + gráficos.

Dependências reais: `clone` vem primeiro (todos os coletores iteram `repos/`);
as 9 coletas são independentes entre si; `dataset` só roda depois de todas;
`ml` depende só do dataset consolidado.

### Machine Learning (parte que merece mais ênfase)

**Pergunta de pesquisa:** *"Métricas de qualidade de código (complexidade,
duplicação, code smells, processo, OO) conseguem prever quais arquivos `.java`
são propensos a risco de segurança?"*

**Métrica-alvo:** `has_security_risk` (binária). Vale **1** se o arquivo foi
sinalizado pelo **Semgrep OU pelo CodeQL** (**união**), e **0** caso contrário.
- Mapeia direto para a dimensão **Segurança** da ISO/IEC 25010.
- Usa **união** (não interseção) de propósito: **maximiza o recall**, porque em
  segurança o pior erro é o falso-negativo (deixar passar um arquivo arriscado).

**Features (41 no total):** todas as colunas numéricas, exceto identificadores e
alvo. Divididas em 3 famílias:
- 20 estruturais do **SonarQube** (Manutenibilidade).
- 14 de **orientação a objetos** do **CK** (Manutenibilidade / Confiabilidade).
- 7 de **processo** do **PyDriller** (Manutenibilidade).

**Regra anti-vazamento (anti-leakage):** nenhuma métrica derivada de segurança
pode ser feature. Por isso `n_semgrep` e `n_codeql` (contagens por ferramenta)
são EXCLUÍDAS das features (seriam circulares), e medidas de segurança do
SonarQube nunca são coletadas. O modelo só "enxerga" qualidade/estrutura/processo.

**O dataset em números (reais):**
- 31.622 arquivos `.java`.
- 10 repositórios (grupos); tamanhos muito desiguais (ghidra ≈ 23,1 mil arquivos;
  datawave ≈ 6,1 mil; menores < 200).
- 560 positivos (`has_security_risk = 1`) → **≈ 1,77 %** → fortemente
  desbalanceado.

**Como treina e como separa treino/teste (ponto-chave):**
- **NÃO** usa split aleatório 70/30. Usa **GroupKFold com 5 dobras, agrupado por
  repositório**: em cada dobra, treina nos arquivos de N-1 repositórios e testa
  nos arquivos do repositório que sobrou. Um repositório nunca está em treino e
  teste ao mesmo tempo.
- **Por quê:** evita vazamento intra-repositório (arquivos do mesmo projeto se
  parecem). Testar em um projeto inteiro nunca visto mede a capacidade real de
  **generalizar para um projeto novo**.
- **Dados de teste vs sintéticos:** a dobra de teste é sempre 100% arquivos
  **reais e intocados**. O único dado artificial é o **SMOTE**, aplicado
  **apenas na dobra de treino** para combater o desbalanceamento. Ou seja:
  treino = reais + sintéticos (SMOTE); teste = só reais.
- Padronização (StandardScaler) ajustada só no treino e usada apenas pela
  Regressão Logística; modelos de árvore usam dados sem escalar.

**5 modelos comparados** (todos com `random_state=42` e tratamento de
desbalanceamento via `class_weight="balanced"` e/ou SMOTE):
Logistic Regression, Decision Tree, Random Forest, XGBoost, LightGBM.

**Métricas de avaliação:** Precision, Recall, F1 e ROC-AUC.
**Por que NÃO usar accuracy:** com 1,77 % de positivos, prever "nada é arriscado"
acertaria ≈ 98 % — alta e inútil.

**Resultados reais (média das dobras):**

| Modelo | Precision | Recall | F1 | ROC-AUC |
|---|---|---|---|---|
| Logistic Regression | 0,089 | 0,644 | 0,155 | 0,785 |
| Decision Tree | 0,098 | 0,408 | 0,150 | 0,719 |
| **Random Forest** | 0,385 | 0,166 | 0,195 | **0,859** |
| XGBoost | 0,319 | 0,136 | 0,168 | 0,820 |
| LightGBM | 0,341 | 0,121 | 0,155 | 0,837 |

**Leitura dos resultados:**
- Random Forest é o melhor modelo (ROC-AUC ≈ 0,859 e maior F1). ROC-AUC bem
  acima de 0,5 **confirma** que métricas de qualidade têm poder preditivo sobre
  risco de segurança.
- Regressão Logística tem o maior recall (0,64): pega mais arquivos arriscados,
  mas com muitos falsos-positivos — útil para triagem manual.
- F1/precision modestos são **esperados e honestos**: problema raro (1,77 %) e
  validado entre projetos diferentes, sem vazamento.

**Interpretabilidade:** após a validação, treina um Random Forest no dataset
inteiro e gera importância de Gini (top 20 features) e gráfico SHAP (beeswarm),
mostrando quais métricas mais pesam na predição.

**Saídas do ML:** `reports/ml_results.csv`, `reports/ml_confusions.csv`, e os
gráficos `roc_curves.png`, `model_comparison.png`, `feature_importance_rf.png`,
`shap_summary.png`.

## Estrutura de slides sugerida (adapte se melhorar)

1. **Capa** — título do projeto, subtítulo (estudo MSR + ISO 25010 + ML), meu
   nome e o curso.
2. **Problema & motivação** — prever risco de segurança em código a partir de
   qualidade; por que isso importa.
3. **Pergunta de pesquisa** — a hipótese central.
4. **Visão geral do projeto** — o que é, 100% estático, 10 repos NSA, ISO 25010.
5. **Ferramentas de análise** — tabela/ícones das ferramentas e seu papel.
6. **Fluxo do pipeline** — diagrama das 13 fases e o que cada uma gera.
7. **O dataset** — 1 linha por arquivo; números reais (31.622 arquivos, 10 repos,
   1,77 % positivos).
8. **A métrica-alvo** — `has_security_risk`, união Semgrep ∪ CodeQL, por que
   união (recall), mapeamento ISO 25010.
9. **As features** — 41 features, 3 famílias (SonarQube/CK/PyDriller) + regra
   anti-vazamento.
10. **Como treinamos** — GroupKFold por repositório (diagrama), por que não é
    split aleatório.
11. **Treino vs teste / dado real vs sintético** — SMOTE só no treino, teste
    100% real.
12. **Modelos & métricas** — os 5 modelos; por que não usar accuracy.
13. **Resultados** — a tabela; destaque do Random Forest (ROC-AUC 0,859).
14. **Interpretabilidade** — Gini + SHAP; quais métricas pesam.
15. **Conclusão** — a hipótese se confirma (qualidade prevê risco); limitações
    (problema raro, estático) e trabalhos futuros.
16. **Slide de encerramento** — obrigado / perguntas.

Comece confirmando a estrutura e então gere o artefato dos slides + as notas do
apresentador.

=== FIM DO PROMPT ===
