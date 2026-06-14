# Relatório comparativo — Postura de segurança (ISO/IEC 25010)
Estudo estático (apenas clone, sem build) de 10 repositórios Java da organização `NationalSecurityAgency`. Valores **brutos e normalizados por KLOC**. Métrica não coletável aparece como ausente/zero — nunca estimada.

**Unidade de análise:** arquivo `.java`. **Total:** 29662 arquivos; **156 com risco de segurança** (0.53%).

## 1. Postura por repositório (bruto + por KLOC)
| repositório | arquivos_java | KLOC_java | achados_seg | achados_por_KLOC | arquivos_em_risco | pct_risco | CVEs_diretos | CVSS_médio | segredos |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ghidra | 15589 | 2046.2 | 275 | 0.13 | 49 | 0.22 | 0 | 0.0 | 0 |
| datawave | 4302 | 565.9 | 173 | 0.31 | 85 | 1.56 | 30 | 0.0 | 191 |
| timely | 359 | 31.1 | 20 | 0.64 | 8 | 1.1 | 1 | 0.0 | 16 |
| emissary | 676 | 67.4 | 12 | 0.18 | 11 | 1.42 | 0 | 0.0 | 33 |
| lemongrenade | 110 | 13.9 | 5 | 0.36 | 2 | 1.59 | 9 | 0.0 | 1 |
| datawave-query-service | 54 | 14.0 | 5 | 0.36 | 1 | 1.85 | 0 | 0.0 | 2 |
| rank-based-linkage | 34 | 1.6 | 3 | 1.82 | 0 | 0.0 | 0 | 0.0 | 0 |
| fractalrabbit | 31 | 1.1 | 3 | 2.72 | 0 | 0.0 | 0 | 0.0 | 0 |
| datawave-audit-service | 48 | 7.7 | 1 | 0.13 | 0 | 0.0 | 0 | 0.0 | 3 |
| datawave-authorization-service | 51 | 3.5 | 1 | 0.29 | 0 | 0.0 | 0 | 0.0 | 5 |

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
| LogisticRegression | 0.0316 | 0.6264 | 0.0597 | 0.7903 | 17.4 | 1053.0 | 13.8 | 4848.2 |
| DecisionTree | 0.0551 | 0.2985 | 0.0902 | 0.6996 | 9.8 | 359.8 | 21.4 | 5541.4 |
| RandomForest | 0.0047 | 0.0082 | 0.0059 | 0.8227 | 0.4 | 17.4 | 30.8 | 5883.8 |
| XGBoost | 0.0 | 0.0 | 0.0 | 0.7839 | 0.0 | 16.8 | 31.2 | 5884.4 |
| LightGBM | 0.0034 | 0.0041 | 0.0037 | 0.795 | 0.2 | 12.2 | 31.0 | 5889.0 |

> Avaliação liderada por **ROC-AUC/Recall/F1** (não accuracy), dado o forte desbalanceamento. Features: complexidade (lizard), OO (CK) e processo (PyDriller) — **nenhuma derivada do alvo** (anti-vazamento).

## Figuras
- `charts/security_per_kloc.png` — densidade de achados por KLOC.
- `charts/cwe_distribution.png` — CWE por sub-característica 25010.
- `charts/posture_heatmap.png` — mapa comparativo da postura.
- `charts/roc_curves.png`, `charts/model_comparison.png`, `charts/feature_importance_rf.png`, `charts/shap_summary.png` — ML.
