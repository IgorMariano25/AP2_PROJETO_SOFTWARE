# Critérios de Seleção de Repositórios — Resumo

**Projeto:** análise estática de qualidade e segurança de código Java (ISO/IEC 25010) com predição por Machine Learning.

O corpus atual usa 10 repositórios da `NationalSecurityAgency`, mas **isso não é uma exigência do método**. Qualquer repositório público do GitHub que atenda aos 5 critérios abaixo pode ser analisado pelo pipeline, independente de organização ou domínio.

---

## Os 5 critérios

| # | Critério | Limiar | Por que é obrigatório |
|---|---|---|---|
| 1 | **Java dominante** | ≥ 70% do LOC | Todas as ferramentas (CK, CodeQL, PyDriller, lizard) são Java-only. Fora disso, o dataset sai vazio. |
| 2 | **Público no GitHub, `owner/repo`** | clone anônimo | Sem LFS ou submódulos, e o nome não pode conter `__` (usado como separador interno de pastas). |
| 3 | **Histórico Git rico** | ≥ 300 commits, ≥ 5 autores, ≥ 2 anos | 7 features de ML vêm do histórico. Histórico *squashed* torna todas constantes. |
| 4 | **Volume adequado** | 200–5.000 arquivos `.java` | Abaixo: sem dados para treinar. Acima: estoura os *timeouts* das ferramentas (o `ghidra`, com 2M LOC, é o caso-limite). |
| 5 | **Código OO com variância** | classes, herança, métodos reais | As métricas CK (CBO, LCOM, DIT) precisam de variação. Só DTOs ou exemplos triviais não geram sinal. |

---

## Pontos de atenção metodológica

**1. Os critérios 1 e 5 protegem as métricas.** Todas as ferramentas do pipeline são específicas para Java, e as métricas CK só produzem sinal em código orientado a objetos com herança e acoplamento reais.

**2. Os critérios 3 e 4 protegem o treino do modelo.** Sem histórico rico, as features de processo viram constantes; sem volume mínimo, não há dados para treinar; sem volume máximo, as ferramentas estouram o *timeout*.

**3. O desenho sem build impõe limites conhecidos.** Analisar apenas o código-fonte (sem compilar) torna o estudo reprodutível e escalável, mas dependências transitivas não são resolvidas e código gerado não é medido. Ambos já constam como limitações declaradas do trabalho.

---