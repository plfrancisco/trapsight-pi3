# CURRENT TASK — CONFIGURAÇÃO DE AMBIENTE — Projeto Integrador

**Versão:** 1.0
**Status:** CONCLUÍDA (2026-10-08)
**Escopo:** o que cada integrante do grupo precisa preparar na própria
máquina antes de qualquer outra task começar

---

# 1. Objetivo

Garantir que qualquer pessoa do grupo consiga clonar o repositório e ter o
projeto rodando localmente, sem depender de conhecimento não documentado.
Esta task é **pré-requisito de todas as outras** — nenhuma task de
`current_task_infra.md` em diante deve ser iniciada antes desta estar
concluída.

Diferença em relação a `current_task_infra.md`: aquela cria a estrutura do
repositório (uma vez, por quem inicia o projeto); esta é o que **cada
integrante** repete na própria máquina para conseguir trabalhar.

---

# 2. Escopo

Cobre pré-requisitos de software, variáveis de ambiente e verificação de que
o ambiente sobe. Não cobre a criação da estrutura de pastas em si
(`current_task_infra.md`, INFRA02) nem a escrita de código de aplicação.

---

# 3. Tarefas

## AMB01 — Pré-requisitos de software

- [x] Git instalado
- [x] Docker Desktop instalado e em execução
- [x] Node.js LTS instalado (para rodar o frontend fora do Docker durante o
      desenvolvimento, se necessário)
- [x] Python 3.11+ instalado
- [x] `uv` instalado (`pip install uv` ou instalador nativo)

**Status: CONCLUÍDA em 2026-09-24** (máquina do Pedro Lucas), confirmada
pelo usuário.

| Ferramenta | Versão verificada |
|---|---|
| Git | 2.55.0 |
| Docker | 29.7.2 (cliente) |
| Node.js | v24.18.0 |
| Python | 3.14.6 |
| uv | 0.12.5 |

- **Docker:** na primeira checagem o motor (daemon) estava parado, e "em
  execução" foi confirmado pelo usuário. Em nova checagem no mesmo dia
  (`docker info`), o daemon respondeu (`server 29.7.2`) — **verificado por
  comando**. A AMB04 (`docker compose up`) continua sendo a verificação
  completa.
- **Decisão sobre o Python:** mantido o 3.14.6 da máquina. **Risco
  conhecido:** o PyTorch e o `segmentation_models_pytorch` podem não ter
  suporte estável para o Python mais recente. Só afeta a trilha de ML
  (`current_task_modelo.md`, ML04). Se ocorrer, fixar uma versão mais antiga
  apenas no projeto via `uv` (ex.: `uv python pin 3.12`), sem alterar o
  Python da máquina.

**Especificação:** `../../plan/foundation/tech_stack.md`, seções 2, 3 e 7.
**Dependências:** nenhuma.

## AMB02 — Clonar e configurar o repositório

- [x] Clonar `https://github.com/plfrancisco/Projeto-Integrador-3-Semestre-`
- [x] Copiar `backend/.env.example` para `backend/.env` e preencher os
      valores de desenvolvimento (ver AMB03)
- [x] Copiar `frontend/.env.example` para `frontend/.env`
- [x] Criar o `.env` da **raiz** (variáveis `POSTGRES_*` do Docker Compose),
      a partir do `.env.example` da raiz

**Status: CONCLUÍDA em 2026-09-24.** `backend/.env`, `frontend/.env` e o
`.env` da raiz criados localmente e confirmados como ignorados pelo Git. As
credenciais do `.env` da raiz devem coincidir com a `DATABASE_URL` de
`backend/.env`. Cada integrante repete este passo na própria máquina.

**Desvio aceito (somente desenvolvimento local):** o usuário do Postgres em
desenvolvimento é `root`, o que o torna superusuário — contraria a
recomendação de menor privilégio de `../../rules/security_spec.md`, seção 6.2.
Aceito porque o banco não publica porta no host e o ambiente não é exposto.
Não replicar em qualquer ambiente fora da máquina de desenvolvimento.

**Especificação:** `../../plan/api/api_spec.md`, seção 2.6.
**Dependências:** AMB01.

## AMB03 — Arquivos de exemplo de variáveis de ambiente

- [x] Criar `backend/.env.example` com as variáveis da tabela abaixo
- [x] Criar `frontend/.env.example` com `VITE_API_URL`
- [x] Confirmar que `.env` (sem `.example`) está no `.gitignore` — nunca
      versionar valores reais

**Status: CONCLUÍDA em 2026-09-24**, aprovada pelo usuário após revisão em
duas rodadas.

- **Arquivos:** `backend/.env.example` (7 variáveis) e
  `frontend/.env.example` (`VITE_API_URL`).
- **Validação:** `.env` ignorado pelo Git, `.env.example` versionável; nomes
  das variáveis idênticos a `api_spec.md`, seção 2.6; nenhum valor com
  aparência de credencial (só `SEU_USUARIO:SUA_SENHA` como placeholder).
- **Decisão registrada:** `MODEL_VERSION=v0.1.0-dev` (o `v1.2.0` da spec era
  exemplo de formato); `api_spec.md` ajustada para coincidir.
- **Pendência:** aviso de acesso negado ao ignore global do Git
  (`~/.config/git/ignore`) — problema de permissão local, não afeta o
  projeto.

**Conteúdo de referência para `backend/.env.example`:**

```text
DATABASE_URL=postgresql://user:senha@db:5432/armadilhas
MODEL_WEIGHTS_PATH=/app/models/checkpoints/latest.pt
MODEL_VERSION=v0.1.0-dev
UPLOADS_DIR=/app/data/uploads
CORS_ORIGENS=http://localhost:5173
LIMIAR_ATENCAO=40
LIMIAR_TROCAR=70
```

**Conteúdo de referência para `frontend/.env.example`:**

```text
VITE_API_URL=http://localhost:8000/api
```

**Especificação:** `../../plan/api/api_spec.md`, seção 2.6 (tabela completa de
variáveis, obrigatoriedade e valores padrão).
**Dependências:** nenhuma — pode ser feita antes de AMB02 por quem primeiro
monta a estrutura, e reaproveitada pelos demais integrantes.

**Nota:** `MODEL_WEIGHTS_PATH` aponta para um arquivo que só existirá após
`current_task_modelo.md` (ML04). Até lá, o backend sobe com o stub de
inferência (`current_task_api.md`, API04), que não depende deste arquivo.

## AMB04 — Verificação

- [x] `docker compose up` sobe sem erro (Postgres, backend, frontend)
- [x] Backend responde em `/docs`
- [x] Frontend carrega em `http://localhost:5173`
- [x] `uv run ruff check .` roda sem erro de configuração (mesmo com poucos
      arquivos ainda)

**Concluída em:** 2026-10-08.
**Dependências:** AMB01, AMB02, AMB03, e a estrutura de
`current_task_infra.md` já criada.

---

# 4. Ordem de execução

AMB01 → AMB02 e AMB03 (podem ser paralelas, mas AMB03 idealmente é feita
uma vez e commitada por quem monta a estrutura inicial) → AMB04.

---

# 5. Critério de conclusão

Todo integrante do grupo tem o projeto rodando localmente via
`docker compose up`, com os três serviços respondendo. Esta task é concluída
por pessoa, não uma vez só pelo grupo — cada novo integrante repete AMB01 a
AMB04.

---

# FIM DA TASK — CONFIGURAÇÃO DE AMBIENTE
