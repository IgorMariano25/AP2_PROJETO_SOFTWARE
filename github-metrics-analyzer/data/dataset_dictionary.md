# Security Dataset — Column Dictionary
| Column | Type | Description | ISO 25010 mapping |
|--------|------|-------------|------------------|
| `repository` | str | GitHub full name of the repository (owner/repo) |  |
| `file` | str | Relative path of the .java file within the repository |  |
| `n_semgrep` | int64 | Number of Semgrep security findings in the file (descriptive; excluded from ML) |  |
| `n_codeql` | int64 | Number of CodeQL security findings in the file (descriptive; excluded from ML) |  |
| `has_security_risk` | int64 | Binary target (ISO 25010 Segurança): 1 = file flagged by Semgrep OR CodeQL (union); 0 = no finding | Segurança |
| `sonar_ncloc` | float64 | Non-comment lines of code (SonarQube) [Manutenibilidade] | Manutenibilidade |
| `sonar_lines` | float64 | — |  |
| `sonar_functions` | float64 | — |  |
| `sonar_classes` | float64 | — |  |
| `sonar_statements` | float64 | — |  |
| `sonar_complexity` | float64 | Cyclomatic complexity (SonarQube) [Manutenibilidade] | Manutenibilidade |
| `sonar_cognitive_complexity` | float64 | Cognitive complexity (SonarQube) [Manutenibilidade] | Manutenibilidade |
| `sonar_duplicated_lines` | float64 | — |  |
| `sonar_duplicated_lines_density` | float64 | % duplicated lines (SonarQube) [Manutenibilidade] | Manutenibilidade |
| `sonar_duplicated_blocks` | float64 | — |  |
| `sonar_comment_lines` | float64 | — |  |
| `sonar_comment_lines_density` | float64 | % comment lines (SonarQube) [Manutenibilidade] | Manutenibilidade |
| `sonar_code_smells` | float64 | Code smells (SonarQube, source-only → partial) [Manutenibilidade] | Manutenibilidade |
| `sonar_sqale_index` | float64 | Technical-debt remediation effort, minutes (SonarQube) |  |
| `sonar_sqale_debt_ratio` | float64 | — |  |
| `sonar_violations` | float64 | Total rule violations (SonarQube, source-only → partial) |  |
| `sonar_blocker_violations` | float64 | — |  |
| `sonar_critical_violations` | float64 | — |  |
| `sonar_major_violations` | float64 | — |  |
| `sonar_minor_violations` | float64 | — |  |
| `wmc` | float64 | Weighted Methods per Class (sum across classes in file) [ISO 25010 Manutenibilidade] | Manutenibilidade |
| `dit` | float64 | Depth of Inheritance Tree (max across classes in file) |  |
| `noc` | float64 | Number of Children (max in file) |  |
| `cbo` | float64 | Coupling Between Objects (max in file) [ISO 25010 Manutenibilidade] | Manutenibilidade |
| `rfc` | float64 | Response For a Class (sum across classes) [ISO 25010 Confiabilidade] | Confiabilidade |
| `lcom` | float64 | Lack of Cohesion in Methods (max in file) |  |
| `lcom_star` | float64 | Normalised LCOM* (max in file) |  |
| `num_methods` | float64 | Total methods per file (CK count) |  |
| `num_static_methods` | float64 | Static methods per file |  |
| `num_fields` | float64 | Total fields per file (CK) |  |
| `num_static_fields` | float64 | Static fields per file |  |
| `tcc` | float64 | Tight Class Cohesion (max in file) [ISO 25010 Manutenibilidade] | Manutenibilidade |
| `lcc` | float64 | Loose Class Cohesion (max in file) |  |
| `num_classes` | float64 | Number of top-level class declarations (CK) |  |
| `commits` | float64 | Number of commits that modified this file [ISO 25010 Manutenibilidade] | Manutenibilidade |
| `distinct_authors` | float64 | Number of distinct developers who touched this file |  |
| `lines_added` | float64 | Total lines added across all commits |  |
| `lines_removed` | float64 | Total lines removed across all commits |  |
| `churn` | float64 | lines_added + lines_removed (total code churn) |  |
| `file_age_days` | float64 | Days between first and last commit of the file |  |
| `days_since_change` | float64 | Days since the most recent commit to the file |  |
