# Artigo SBC — Análise de segurança de repositórios Java da NSA (ISO/IEC 25010 + ML)

Artigo científico no padrão **SBC** (6–10 páginas), pronto para o Overleaf.

## Arquivos

| Arquivo | Conteúdo |
|---|---|
| `main.tex` | Corpo do artigo (Introdução → Conclusão), já com os números reais do estudo |
| `referencias.bib` | Bibliografia (obras reais; **verificar antes de submeter** — ver abaixo) |
| `sbc-template.sty` / `sbc.bst` | Arquivos de estilo necessários para compilar no padrão SBC |
| `figuras/` | Figuras usadas no artigo e figuras complementares geradas pelo pipeline |

## Como compilar

O artigo usa o padrão SBC (`sbc-template`). Esta pasta já inclui os arquivos
`sbc-template.sty` e `sbc.bst` necessários para compilar o projeto no Overleaf
ou localmente.

### Opção A — Overleaf (recomendada)
1. No Overleaf, crie um projeto vazio ou a partir do template oficial
   **"SBC – Sociedade Brasileira de Computação (Conferences)"**.
2. Faça upload de `main.tex`, `referencias.bib`, `sbc-template.sty`, `sbc.bst`
   e da pasta `figuras/`.
3. Compile com **pdfLaTeX**.

### Opção B — Local
1. A partir desta pasta, rode:
   ```bash
   pdflatex main && bibtex main && pdflatex main && pdflatex main
   ```

## ⚠️ Verificação de referências (exigência do enunciado)

Todas as entradas de `referencias.bib` correspondem a **obras reais e
consolidadas** (ISO 25000/25010/25023; McCabe 1976; Chidamber & Kemerer 1994;
PyDriller/Spadini 2018; Shin 2011; Zimmermann 2010; Walden 2014; SMOTE/Chawla
2002; Random Forest/Breiman 2001; XGBoost/Chen & Guestrin 2016; LightGBM/Ke et
al. 2017; SHAP/Lundberg & Lee 2017). **Confira autores, ano, páginas e DOI na fonte primária antes da
submissão** — DOIs foram omitidos onde não verificáveis para não fabricar.

## Fonte dos números

Os valores citados no artigo vêm de:
- `../github-metrics-analyzer/reports/comparative_report.md` (postura por repo, CWE, sub-características)
- `../github-metrics-analyzer/reports/ml_results.csv` (desempenho dos modelos)
- `../github-metrics-analyzer/data/security_dataset.csv` (31.622 arquivos, 560 positivos)

Para regenerar tudo: `python scripts/run_all.py` seguido de
`python scripts/generate_comparative_report.py`.
