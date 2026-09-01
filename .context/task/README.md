# ÍNDICE DE TASKS — Projeto Integrador

**Versão:** 1.0
**Status:** ATIVO
**Escopo:** controle de execução e precedência entre tasks

---

# 1. Objetivo

Este índice define qual documento controla a execução. A existência de uma
task histórica ou futura não autoriza implementação.

---

# 2. Fonte canônica

Tasks são organizadas por especialidade — cada arquivo é a única fonte de
ordem, checkbox e status para seu domínio. Um arquivo nunca detalha task de
outra especialidade, mesmo quando há dependência entre elas — a dependência
é referenciada, nunca duplicada.

| Arquivo | Estado | Especialidade |
|---|---|---|
| `current_task_frontend.md` | ATIVA | Interface web — as 4 telas do MVP |
| `current_task_modelo.md` | ATIVA | Especificação de treino, dataset sintético, baseline, treino da U-Net, avaliação |
| `current_task_seed_demo.md` | ATIVA | Script de seed com os seis cenários de demonstração |
| `current_task_externo.md` | ATIVA | Material da empresa parceira, entrevista, integrantes e prazo |

---

# 3. Documentos históricos

Arquivos concluídos ficam em `completed/`, fora do fluxo de execução ativo.
Não podem ser alterados sem autorização explícita.

| Arquivo | Escopo | Concluída em |
|---|---|---|
| `completed/current_task_api.md` | Backend FastAPI — endpoints, erros padronizados, stub de inferência, projeção de saturação, upload e mídia | 2026-10-08 |
| `completed/current_task_ambiente.md` | Configuração local, arquivos de ambiente e verificação do ambiente completo | 2026-10-08 |
| `completed/current_task_infra.md` | Ambiente Python, estrutura de pastas, Docker Compose | 2026-10-02 |
| `completed/current_task_banco.md` | Migration, entidades ORM, regra de integridade do refil ativo | 2026-10-02 |

---

# 4. Precedência

1. `.context/rules/ai_development_rules.md`
2. documentos normativos em `.context/plan/`
3. `completed/current_task_ambiente.md` — pré-requisito de todas as tasks
4. arquivo de task **ativo** da especialidade em questão
5. arquivos históricos, somente para contexto

Conflito entre task e documento normativo deve ser apresentado ao usuário e
corrigido antes da implementação.

---

# FIM DO ÍNDICE DE TASKS
