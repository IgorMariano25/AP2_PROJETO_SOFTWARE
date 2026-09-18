# Relatório comparativo — Postura de segurança (ISO/IEC 25010)
Estudo estático (apenas clone, sem build) de 10 repositórios Java da organização `NationalSecurityAgency`. Valores **brutos e normalizados por KLOC**. Métrica não coletável aparece como ausente/zero — nunca estimada.

**Unidade de análise:** arquivo `.java`. **Total:** 64415 arquivos; **839 com risco de segurança** (1.30%).

## 1. Postura por repositório (bruto + por KLOC)
| repositório | arquivos_java | KLOC_java | achados_seg | achados_por_KLOC | arquivos_em_risco | pct_risco | CVEs_diretos | CVSS_médio | segredos |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| netty | 3589 | 430.0 | 376 | 0.87 | 143 | 1.65 | 0 | 0.0 | 286 |
| dubbo | 3986 | 309.4 | 297 | 0.96 | 71 | 0.61 | 0 | 0.0 | 50 |
| nacos | 5249 | 532.7 | 218 | 0.41 | 177 | 1.95 | 6 | 0.0 | 127 |
| thingsboard | 4780 | 406.7 | 81 | 0.2 | 167 | 1.37 | 1 | 0.0 | 2247 |
| zookeeper | 943 | 126.7 | 56 | 0.44 | 50 | 1.56 | 0 | 0.0 | 366 |
| rocketmq | 2287 | 287.4 | 54 | 0.19 | 37 | 0.74 | 0 | 0.0 | 35 |
| shiro | 847 | 44.2 | 53 | 1.2 | 40 | 0.96 | 0 | 0.0 | 49 |
| jenkins | 1946 | 208.5 | 52 | 0.25 | 110 | 2.32 | 0 | 0.0 | 248 |
| httpcomponents-client | 1170 | 119.6 | 41 | 0.34 | 31 | 0.68 | 0 | 0.0 | 386 |
| commons-compress | 709 | 83.3 | 2 | 0.02 | 13 | 1.15 | 0 | 0.0 | 11 |

> Três repositórios (`datawave`, `datawave-query-service`, `datawave-audit-service`, `datawave-authorization-service`) pertencem ao ecossistema **DataWave** — variável de confusão / limitação de validade externa (Seção de limitações).

## 2. Distribuição de CWE → sub-característica ISO/IEC 25010
| CWE | achados | sub_característica_25010 |
| --- | --- | --- |
| CWE-353 | 379 | Outras/Não classificada |
| CWE-1357 | 358 | Outras/Não classificada |
| CWE-732 | 252 | Outras/Não classificada |
| CWE-319 | 117 | Confidencialidade |
| CWE-1333 | 83 | Outras/Não classificada |
| CWE-470 | 81 | Integridade |
| CWE-79 | 45 | Integridade |
| CWE-134 | 29 | Outras/Não classificada |
| CWE-89 | 26 | Integridade |
| CWE-915 | 25 | Outras/Não classificada |
| CWE-328 | 20 | Confidencialidade |
| CWE-829 | 20 | Outras/Não classificada |
| CWE-352 | 16 | Outras/Não classificada |
| CWE-78 | 15 | Integridade |
| CWE-326 | 14 | Confidencialidade |
| CWE-284 | 14 | Outras/Não classificada |
| CWE-345 | 12 | Outras/Não classificada |
| CWE-330 | 12 | Outras/Não classificada |
| CWE-798 | 9 | Autenticidade |
| CWE-116 | 8 | Outras/Não classificada |
| CWE-614 | 7 | Confidencialidade |
| CWE-676 | 7 | Outras/Não classificada |
| CWE-295 | 6 | Autenticidade |
| CWE-1004 | 6 | Confidencialidade |
| CWE-327 | 5 | Confidencialidade |
| CWE-22 | 4 | Integridade |
| CWE-502 | 3 | Integridade |
| CWE-611 | 3 | Integridade |
| CWE-95 | 2 | Outras/Não classificada |
| CWE-321 | 2 | Outras/Não classificada |
| CWE-94 | 2 | Integridade |
| CWE-704 | 1 | Outras/Não classificada |
| CWE-601 | 1 | Outras/Não classificada |
| CWE-150 | 1 | Outras/Não classificada |
| CWE-200 | 1 | Confidencialidade |
| CWE-939 | 1 | Outras/Não classificada |
| CWE-96 | 1 | Outras/Não classificada |

## 3. Cobertura das sub-características de Segurança (25010)
| sub_característica (25010) | evidências (achados/CVEs) | fonte |
| --- | --- | --- |
| Integridade | 179 | Semgrep (SAST por arquivo) |
| Confidencialidade | 170 | Semgrep (SAST por arquivo) |
| Autenticidade | 15 | Semgrep (SAST por arquivo) |
| Resistência | 7 | OSV-Scanner (dependências) |
| Outras/Não classificada | 1224 | Semgrep (SAST por arquivo) |

> **Não-repúdio** e **Responsabilização** não são mensuráveis por SAST/SCA estática → discussão qualitativa/limitação. **Safety** (25010:2023) não é medida por nenhuma ferramenta deste estudo.

## 4. Severidade dos achados (Semgrep)
| severidade | achados |
| --- | --- |
| WARNING | 1088 |
| ERROR | 93 |
| INFO | 29 |
| MEDIUM | 20 |

## 5. Predição por ML (GroupKFold por repositório)
| model | precision | recall | f1 | roc_auc | tp | fp | fn | tn |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| LogisticRegression | 0.0569 | 0.7535 | 0.1053 | 0.8928 | 129.8 | 2199.2 | 38.0 | 10516.0 |
| DecisionTree | 0.0838 | 0.3985 | 0.1356 | 0.8064 | 67.2 | 791.8 | 100.6 | 11923.4 |
| RandomForest | 0.1748 | 0.0985 | 0.1174 | 0.8907 | 16.0 | 72.6 | 151.8 | 12642.6 |
| XGBoost | 0.1614 | 0.062 | 0.0859 | 0.8615 | 10.0 | 54.8 | 157.8 | 12660.4 |
| LightGBM | 0.1773 | 0.0624 | 0.0893 | 0.8723 | 10.4 | 48.6 | 157.4 | 12666.6 |

> Avaliação liderada por **ROC-AUC/Recall/F1** (não accuracy), dado o forte desbalanceamento. Features: complexidade (lizard), OO (CK) e processo (PyDriller) — **nenhuma derivada do alvo** (anti-vazamento).

## Figuras
- `charts/security_per_kloc.png` — densidade de achados por KLOC.
- `charts/cwe_distribution.png` — CWE por sub-característica 25010.
- `charts/posture_heatmap.png` — mapa comparativo da postura.
- `charts/roc_curves.png`, `charts/model_comparison.png`, `charts/feature_importance_rf.png`, `charts/shap_summary.png` — ML.
