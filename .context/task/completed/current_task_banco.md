# CURRENT TASK — BANCO DE DADOS — Projeto Integrador

**Versão:** 1.0
**Status:** CONCLUÍDA (2026-10-02)
**Escopo:** migration inicial, entidades ORM, repositórios e regras de
integridade

---

# 1. Objetivo

Implementar o modelo de dados definido em `data_model.md`: as três tabelas
do MVP, a camada de acesso e a regra de integridade que sustenta a série
temporal do projeto.

---

# 2. Escopo

Cobre `armadilha`, `refil` e `analise`. Não cobre `estabelecimento`
(Fase 2, fora do MVP) nem o script de seed de demonstração, que tem task
própria (`../current_task_seed_demo.md`) por depender do gerador de dataset
sintético.

---

# 3. Tarefas

## DB01 — Migration inicial

- [x] Migration Alembic criando `armadilha`, `refil`, `analise`
- [x] Tipos e defaults conforme especificação (`uuid`, `timestamptz`,
      `numeric(5,2)`)
- [x] Confirmar que toda alteração futura de schema também passa por
      migration — nunca alteração manual

**Especificação:** `../../plan/data/data_model.md`, seções 5 e 6.
**Dependências:** `current_task_infra.md` (INFRA01).
**Concluída em:** 2026-09-24.

## DB02 — Entidades e repositórios

- [x] Entidades SQLAlchemy mapeando as três tabelas
- [x] Repositórios com as operações de leitura/escrita necessárias à API
- [x] Entidades em `src/entities/`, não em `src/networks/`

**Especificação:** `../../plan/data/data_model.md`, seção 6.
**Dependências:** DB01.
**Concluída em:** 2026-10-02.

## DB03 — Regra de integridade: refil ativo único

- [x] Constraint ou verificação que impede duas linhas de `refil` com
      `data_troca IS NULL` para a mesma `armadilha_id`
- [x] Teste automatizado cobrindo a regra

**Especificação:** `../../plan/data/data_model.md`, seção 6.3.
**Dependências:** DB02.
**Concluída em:** 2026-10-02.

**Nota:** esta regra sustenta a série temporal do projeto inteiro. Sem ela,
duas análises simultâneas em refis diferentes da mesma armadilha
corromperiam o gráfico de evolução e a projeção de saturação
(`../../plan/frontend/telas_spec.md`, seção 5).

---

# 4. Ordem de execução

DB01 → DB02 → DB03, sequencial — cada uma depende da anterior.

---

# 5. Critério de conclusão

Migration aplicada, entidades e repositórios cobrindo as operações que a API
vai consumir (ver `current_task_api.md`), regra de integridade coberta por
teste que falha ao tentar criar um segundo refil ativo.

---

# FIM DA TASK — BANCO DE DADOS
