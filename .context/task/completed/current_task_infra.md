# CURRENT TASK — INFRAESTRUTURA — Projeto Integrador

**Versão:** 1.0
**Status:** CONCLUÍDA (2026-10-02)
**Escopo:** ambiente de desenvolvimento, estrutura de pastas e orquestração
Docker

---

# 1. Objetivo

Preparar o ambiente e a estrutura de repositório sobre os quais backend,
frontend e modelo serão construídos. Nenhuma outra task depende de código
funcional aqui — apenas da estrutura existir.

---

# 2. Escopo

Cobre ambiente Python, estrutura de pastas e Docker Compose. Não cobre
código de aplicação (backend, frontend, modelo) nem o pipeline de treino,
que roda fora do Docker por decisão registrada em `tech_stack.md`, seção 6.1.

**Pré-requisito:** `current_task_ambiente.md` concluída pela pessoa que vai
executar esta task — pré-requisitos de software instalados antes de
inicializar qualquer coisa aqui.

---

# 3. Tarefas

## INFRA01 — Ambiente Python

- [x] Inicializar projeto com `uv` e `pyproject.toml`
- [x] Gerar lockfile e exportar `requirements.txt` para o build Docker
- [x] Configurar Ruff como linter/formatter

**Status: CONCLUÍDA em 2026-09-24**, aprovada após revisão em duas rodadas.
Ruff 0.16.8 como única dependência (grupo `dev`); `requires-python =
">=3.11"` conforme a spec (a primeira versão usava `>=3.14`, corrigida por
quebrar a instalação de integrantes com Python mais antigo). `requirements.txt`
sem dependências de aplicação, por ainda não existirem.

**Especificação:** `../../plan/foundation/tech_stack.md`, seção 7.
**Dependências:** nenhuma.

## INFRA02 — Estrutura de pastas

- [x] Criar `backend/src/{api,entities,repositories,inference,networks,config}`
- [x] Criar `backend/training/`, `backend/migrations/`
- [x] Criar `frontend/src/{components,pages,services}`
- [x] Criar `data/` e `models/` (fora do versionamento, conforme `.gitignore`)
- [x] Criar `notebooks/`

**Status: CONCLUÍDA em 2026-09-24.** Durante a revisão, o Codex apontou que
o `.gitignore` não cobria `data/` e `models/` por completo; corrigido com
`data/*` e `models/*`, mantendo apenas os `.gitkeep`. Sem isso, dataset ou
material da empresa parceira poderiam ir para o repositório público.

**Especificação:** `../../plan/foundation/tech_stack.md`, seção 8.
**Dependências:** nenhuma.

**Nota:** a rede neural vai em `src/networks/`, não em `src/models/` —
entidades ORM ficam em `src/entities/`. A ambiguidade entre os dois sentidos
de "models" (ORM vs. rede) está resolvida em `tech_stack.md`, seção 8, e não
deve ser reaberta.

## INFRA03 — Docker Compose

- [x] `docker-compose.yml` orquestrando PostgreSQL, backend (FastAPI) e
      frontend (React)
- [x] Volume Docker para `data/uploads/`
- [x] Volume Docker para `models/checkpoints/` (pesos do modelo)
- [x] Containers de backend e frontend rodando com usuário não-root
- [x] Imagens base mínimas, nenhum segredo copiado em tempo de build

**Status: CONCLUÍDA em 2026-09-24**, aprovada após revisão.

- **Arquivos:** `docker-compose.yml`, `.env.example` (raiz), `backend/Dockerfile`,
  `frontend/Dockerfile` e os dois `.dockerignore`.
- **Segurança:** credenciais do Postgres só via `.env` da raiz, sem valor
  padrão (o compose recusa subir sem elas); portas presas em `127.0.0.1`;
  Postgres sem porta publicada; pesos do modelo montados como somente
  leitura; usuários não-root.
- **Validado:** `docker compose config`, Postgres `healthy`, build do
  backend.
- **Não validável ainda (esperado):** backend permanecer de pé (depende da
  API01, `src.main:app`) e build do frontend (depende da FE01,
  `package.json`). A verificação completa é a AMB04.
- **Desvio aceito:** `POSTGRES_USER=root` é superusuário; ver
  `current_task_ambiente.md`, AMB02.
- **Observação:** em hosts Linux, o bind mount `./data/uploads` é criado como
  root e o usuário `app` do container pode não conseguir gravar. Não afeta
  Windows/Docker Desktop.

**Especificação:** `../../plan/foundation/tech_stack.md`, seção 6.1;
`../../rules/security_spec.md`, seções 3 e 10.1.
**Dependências:** INFRA01, INFRA02.

**Nota:** o treino do modelo **não** roda em container — GPU passthrough via
WSL2 não compensa o esforço de configuração no escopo deste projeto.

---

# 4. Ordem de execução

INFRA01 e INFRA02 podem rodar em paralelo. INFRA03 depende de ambos.

---

# 5. Critério de conclusão

Ambiente sobe com `docker compose up`, backend e frontend respondem (mesmo
vazios), Postgres aceita conexão, e a estrutura de pastas está criada
conforme especificado.

---

# FIM DA TASK — INFRAESTRUTURA
