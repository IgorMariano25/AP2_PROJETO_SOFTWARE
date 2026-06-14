# Artigo SBC — Análise de segurança de repositórios Java da NSA (ISO/IEC 25010 + ML)

Artigo científico no padrão **SBC** (6–10 páginas), pronto para o Overleaf.

## Arquivos

| Arquivo | Conteúdo |
|---|---|
| `main.tex` | Corpo do artigo (Introdução → Conclusão), já com os números reais do estudo |
| `referencias.bib` | Bibliografia (obras reais; **verificar antes de submeter** — ver abaixo) |
| `figuras/` | 7 figuras geradas pelo pipeline (ROC, importância de features, SHAP, CWE, KLOC, heatmap, comparação) |

## Como compilar

O artigo usa o **template oficial da SBC** (`sbc-template`), que fornece os
arquivos `sbc-template.sty` e `sbc.bst`. **Eles não são incluídos aqui** (são
distribuídos pela SBC) — use uma das opções:

### Opção A — Overleaf (recomendada)
1. No Overleaf, crie um projeto a partir do template oficial
   **"SBC – Sociedade Brasileira de Computação (Conferences)"**.
2. Substitua o `main.tex` do template pelo `main.tex` desta pasta.
3. Faça upload de `referencias.bib` e da pasta `figuras/`.
4. Compile com **pdfLaTeX** (o template já traz `sbc-template.sty` e `sbc.bst`).

### Opção B — Local
1. Baixe o pacote do template SBC (`sbc-template.sty`, `sbc.bst`) do site da SBC.
2. Coloque-os nesta pasta e rode:
   ```bash
   pdflatex main && bibtex main && pdflatex main && pdflatex main
   ```

## ⚠️ Verificação de referências (exigência do enunciado)

Todas as entradas de `referencias.bib` correspondem a **obras reais e
consolidadas** (ISO 25000/25010/25023; McCabe 1976; Chidamber & Kemerer 1994;
PyDriller/Spadini 2018; Shin 2011; Zimmermann 2010; Walden 2014; SMOTE/Chawla
2002; Random Forest/Breiman 2001; XGBoost/Chen & Guestrin 2016; SHAP/Lundberg &
Lee 2017). **Confira autores, ano, páginas e DOI na fonte primária antes da
submissão** — DOIs foram omitidos onde não verificáveis para não fabricar.

## Fonte dos números

Os valores citados no artigo vêm de:
- `../github-metrics-analyzer/reports/comparative_report.md` (postura por repo, CWE, sub-características)
- `../github-metrics-analyzer/reports/ml_results.csv` (desempenho dos modelos)
- `../github-metrics-analyzer/data/security_dataset.csv` (29.662 arquivos, 156 positivos)

Para regenerar tudo: `python scripts/run_all.py` seguido de
`python scripts/generate_comparative_report.py`.
