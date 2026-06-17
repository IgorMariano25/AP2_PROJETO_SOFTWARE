# Relatório comparativo — Postura de segurança (ISO/IEC 25010)
Estudo estático (apenas clone, sem build) de 10 repositórios Java da organização `NationalSecurityAgency`. Valores **brutos e normalizados por KLOC**. Métrica não coletável aparece como ausente/zero — nunca estimada.

**Unidade de análise:** arquivo `.java`. **Total:** 31622 arquivos; **560 com risco de segurança** (1.77%).

## 1. Postura por repositório (bruto + por KLOC)
| repositório | arquivos_java | KLOC_java | achados_seg | achados_por_KLOC | arquivos_em_risco | pct_risco | CVEs_diretos | CVSS_médio | segredos |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ghidra | 15589 | 2046.2 | 275 | 0.13 | 253 | 1.09 | 0 | 0.0 | 288 |
| datawave | 4302 | 565.9 | 173 | 0.31 | 221 | 3.61 | 30 | 0.0 | 201 |
| timely | 359 | 31.1 | 20 | 0.64 | 19 | 2.42 | 1 | 0.0 | 28 |
| emissary | 676 | 67.4 | 12 | 0.18 | 45 | 5.39 | 0 | 0.0 | 32 |
| lemongrenade | 110 | 13.9 | 5 | 0.36 | 3 | 1.79 | 9 | 0.0 | 1 |
| datawave-query-service | 54 | 14.0 | 5 | 0.36 | 6 | 8.82 | 0 | 0.0 | 2 |
| rank-based-linkage | 34 | 1.6 | 3 | 1.82 | 1 | 0.53 | 0 | 0.0 | 0 |
| fractalrabbit | 31 | 1.1 | 3 | 2.72 | 2 | 1.19 | 0 | 0.0 | 0 |
| datawave-audit-service | 48 | 7.7 | 1 | 0.13 | 4 | 5.88 | 0 | 0.0 | 5 |
| datawave-authorization-service | 51 | 3.5 | 1 | 0.29 | 6 | 8.45 | 0 | 0.0 | 8 |

> Três repositórios (`datawave`, `datawave-query-service`, `datawave-audit-service`, `datawave-authorization-service`) pertencem ao ecossistema **DataWave** — variável de confusão / limitação de validade externa (Seção de limitações).

## 2. Distribuição de CWE → sub-característica ISO/IEC 25010
| CWE | achados | sub_característica_25010 |
| --- | --- | --- |
| CWE-470 | 118 | Integridade |
| CWE-319 | 104 | Confidencialidade |
| CWE-89 | 97 | Integridade |
| CWE-78 | 43 | Integridade |
| CWE-269 | 19 | Outras/Não classificada |
| CWE-20 | 18 | Outras/Não classificada |
| CWE-95 | 17 | Outras/Não classificada |
| CWE-353 | 17 | Outras/Não classificada |
| CWE-502 | 15 | Integridade |
| CWE-1333 | 9 | Outras/Não classificada |
| CWE-295 | 7 | Autenticidade |
| CWE-798 | 4 | Autenticidade |
| CWE-732 | 4 | Outras/Não classificada |
| CWE-611 | 3 | Integridade |
| CWE-1004 | 3 | Confidencialidade |
| CWE-614 | 3 | Confidencialidade |
| CWE-352 | 3 | Outras/Não classificada |
| CWE-328 | 3 | Confidencialidade |
| CWE-326 | 3 | Confidencialidade |
| CWE-96 | 2 | Outras/Não classificada |
| CWE-330 | 2 | Outras/Não classificada |
| CWE-667 | 2 | Outras/Não classificada |
| CWE-704 | 1 | Outras/Não classificada |
| CWE-327 | 1 | Confidencialidade |

## 3. Cobertura das sub-características de Segurança (25010)
| sub_característica (25010) | evidências (achados/CVEs) | fonte |
| --- | --- | --- |
| Integridade | 276 | Semgrep (SAST por arquivo) |
| Confidencialidade | 117 | Semgrep (SAST por arquivo) |
| Autenticidade | 11 | Semgrep (SAST por arquivo) |
| Resistência | 40 | OSV-Scanner (dependências) |
| Outras/Não classificada | 94 | Semgrep (SAST por arquivo) |

> **Não-repúdio** e **Responsabilização** não são mensuráveis por SAST/SCA estática → discussão qualitativa/limitação. **Safety** (25010:2023) não é medida por nenhuma ferramenta deste estudo.

## 4. Severidade dos achados (Semgrep)
| severidade | achados |
| --- | --- |
| WARNING | 376 |
| ERROR | 122 |

## 5. Predição por ML (GroupKFold por repositório)
| model | precision | recall | f1 | roc_auc | tp | fp | fn | tn |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| LogisticRegression | 0.089 | 0.6442 | 0.155 | 0.7847 | 60.6 | 716.4 | 51.4 | 5496.0 |
| DecisionTree | 0.0984 | 0.4083 | 0.1495 | 0.7187 | 37.2 | 295.4 | 74.8 | 5917.0 |
| RandomForest | 0.3852 | 0.1655 | 0.1945 | 0.8594 | 16.2 | 50.8 | 95.8 | 6161.6 |
| XGBoost | 0.3191 | 0.1361 | 0.1683 | 0.8201 | 14.2 | 28.4 | 97.8 | 6184.0 |
| LightGBM | 0.3405 | 0.1209 | 0.1547 | 0.8374 | 14.2 | 33.2 | 97.8 | 6179.2 |

> Avaliação liderada por **ROC-AUC/Recall/F1** (não accuracy), dado o forte desbalanceamento. Features: complexidade (lizard), OO (CK) e processo (PyDriller) — **nenhuma derivada do alvo** (anti-vazamento).

## Figuras
- `charts/security_per_kloc.png` — densidade de achados por KLOC.
- `charts/cwe_distribution.png` — CWE por sub-característica 25010.
- `charts/posture_heatmap.png` — mapa comparativo da postura.
- `charts/roc_curves.png`, `charts/model_comparison.png`, `charts/feature_importance_rf.png`, `charts/shap_summary.png` — ML.
