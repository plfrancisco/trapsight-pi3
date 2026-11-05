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
| `current_task_pwa.md` | PROPOSTA | PWA instalável e envio de foto pela câmera do celular. Não autoriza implementação até o mantenedor confirmar as decisões D1 a D4 |

As duas tasks anteriores (modelo e autenticação com hospedagem) foram arquivadas em `completed/` em 05/11/2026; os itens que ficaram em aberto estão como pendências no Trello. Uma nova frente de trabalho nasce como `current_task_<especialidade>.md` neste diretório, depois de aprovada.

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
| `completed/current_task_frontend.md` | Interface web — as 4 telas do MVP | 2026-10-22 |
| `completed/current_task_seed_demo.md` | Script de seed com os seis cenários de demonstração | 2026-10-21 |
| `completed/current_task_externo.md` | Material da empresa parceira, entrevista, integrantes, prazo, provedor e domínio | 2026-10-28 |
| `completed/current_task_modelo.md` | Especificação de treino, dataset sintético, baseline, treino da U-Net, avaliação e inferência real (ONNX) | arquivada em 2026-11-05 (itens abertos no Trello) |
| `completed/current_task_autenticacao_hospedagem.md` | Login, proteção da API, hospedagem pública (Vercel e Supabase) e verificação de segurança | arquivada em 2026-11-05 (itens abertos no Trello) |

---

# 4. Precedência

1. `.context/rules/ai_development_rules.md`
2. documentos normativos em `.context/plan/`
3. `completed/current_task_ambiente.md` — pré-requisito de todas as tasks
4. arquivo de task **ativo** da especialidade em questão, quando houver
5. arquivos históricos, somente para contexto

Conflito entre task e documento normativo deve ser apresentado ao usuário e
corrigido antes da implementação.

---

# FIM DO ÍNDICE DE TASKS
