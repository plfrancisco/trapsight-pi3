# ÍNDICE DE PLANEJAMENTO — Projeto Integrador

**Versão:** 1.0
**Status:** ATIVO
**Escopo:** índice dos documentos normativos do projeto

---

# 1. Objetivo

Esta pasta reúne os documentos normativos do projeto. Leia somente o conjunto
necessário para a tarefa atual e mantenha as decisões alinhadas a eles.

---

# 2. Estrutura

```text
plan/
├── foundation/  # visão geral, arquitetura e diretrizes do projeto
├── data/        # banco, fontes de dados e modelo de dados
├── model/       # arquitetura do modelo e pipeline de inferência
├── frontend/    # telas da interface e comportamento esperado
└── api/         # contrato REST entre frontend e backend
```

---

# 3. Ordem de leitura recomendada

1. `foundation/project_overview.md`
2. documento da área afetada
3. `.context/rules/ai_development_rules.md`
4. task aplicável em `.context/task/`

---

# 4. Documentos por domínio

| Domínio | Documento | Uso |
|---|---|---|
| Fundação | `foundation/project_overview.md` | Problema, escopo, abordagem técnica |
| Fundação | `foundation/proposta_individual.md` | Proposta individual de solução (formulário acadêmico) |
| Fundação | `foundation/tech_stack.md` | Stack tecnológica, estrutura de pastas e decisões de ferramentas |
| Fundação | `foundation/hardware_armadilha.md` | Especificações do equipamento real (StickFly K-45) e implicações para a visão computacional |
| Fundação | `foundation/stakeholder_evidencias.md` | Contato real com a empresa parceira, evidências confirmadas e hipóteses ainda não validadas |
| Dados | `data/data_model.md` | Modelo de dados, entidades e regras de persistência |
| Dados | `data/seed_demo.md` | Cenários de dados para a apresentação |
| Dados | `data/dataset_sintetico.md` | Geração do dataset sintético — fonte de sprites, composição, metadados, critérios de aceite |
| Modelo | `model/modelo_spec.md` | Classes de segmentação, pré-processamento, cálculo do percentual e carregamento de pesos |
| Modelo | `model/avaliacao_spec.md` | Divisão dos conjuntos, métricas e critérios de aprovação |
| Frontend | `frontend/telas_spec.md` | Telas, conteúdo e comportamento esperado |
| API | `api/api_spec.md` | Contrato REST — endpoints, payloads e erros |

---

# FIM DO ÍNDICE DE PLANEJAMENTO
