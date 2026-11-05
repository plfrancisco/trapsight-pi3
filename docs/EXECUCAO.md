# Guia de execução

Este guia leva do `git clone` ao TrapSight funcionando na sua máquina, e depois mostra como rodar os testes, treinar o modelo e publicar. Se você só quer ver o sistema funcionando, siga as seções 1 a 5.

- [1. Pré-requisitos](#1-pré-requisitos)
- [2. Configurar as variáveis de ambiente](#2-configurar-as-variáveis-de-ambiente)
- [3. Subir o sistema](#3-subir-o-sistema)
- [4. Criar o primeiro gerente e entrar](#4-criar-o-primeiro-gerente-e-entrar)
- [5. Escolher o motor de inferência](#5-escolher-o-motor-de-inferência)
- [6. Desenvolver sem Docker](#6-desenvolver-sem-docker)
- [7. Rodar os testes](#7-rodar-os-testes)
- [8. Dados de demonstração](#8-dados-de-demonstração)
- [9. Treinar e exportar o modelo](#9-treinar-e-exportar-o-modelo)
- [10. Publicar na internet](#10-publicar-na-internet)
- [11. Produção local, segurança e backup](#11-produção-local-segurança-e-backup)
- [12. Problemas comuns](#12-problemas-comuns)

## 1. Pré-requisitos

| Para | Você precisa de |
| --- | --- |
| Rodar o sistema (seções 1 a 5) | [Docker Desktop](https://www.docker.com/products/docker-desktop/) com Compose v2 |
| Desenvolver o backend fora do Docker | [`uv`](https://docs.astral.sh/uv/) (instala o Python 3.12 por conta própria) |
| Desenvolver o frontend fora do Docker | Node.js 24 e npm |
| Rodar `scripts/*.sh` no Windows | Git Bash (vem com o Git para Windows) |
| Treinar o modelo | Placa NVIDIA com CUDA e os dados descritos na seção 9 |

Portas usadas no seu computador: `5173` (frontend), `8000` (API) e `5432` (PostgreSQL). Todas ficam presas ao `127.0.0.1`, ou seja, não ficam expostas à rede.

## 2. Configurar as variáveis de ambiente

Os três arquivos `.env` são ignorados pelo Git. Copie os exemplos:

```bash
cp .env.example .env
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

**`.env` da raiz** define o usuário, a senha e o nome do banco que o Compose cria:

```ini
POSTGRES_USER=trapsight
POSTGRES_PASSWORD=<escolha uma senha>
POSTGRES_DB=armadilhas
```

**`backend/.env`** precisa repetir esses valores na `DATABASE_URL`. O host é `db`, o nome do serviço no Compose:

```ini
DATABASE_URL=postgresql://trapsight:<a mesma senha>@db:5432/armadilhas
```

Os demais valores do `backend/.env.example` já servem para desenvolvimento local. As variáveis mais úteis:

| Variável | Para que serve | Padrão no exemplo |
| --- | --- | --- |
| `INFERENCE_MODE` | Motor de inferência: `stub`, `onnx` ou `modelo` (ver seção 5) | `stub` |
| `MODEL_VERSION` | Versão do modelo, obrigatória | `v0.1.0-dev` |
| `MODEL_WEIGHTS_PATH` | Checkpoint do modo `modelo`; vazio no modo `onnx` usa o modelo empacotado | `/app/models/checkpoints/latest.pt` |
| `LIMIAR_ATENCAO` / `LIMIAR_TROCAR` | Cobertura (%) em que o status vira atenção e trocar | `10` / `20` |
| `CORS_ORIGENS` | Origem do frontend aceita pela API | `http://localhost:5173` |
| `STORAGE_BACKEND` | `filesystem` (pasta `data/uploads`) ou `database` | `filesystem` |
| `FUSO_PRODUTO` | Fuso que define o "hoje" na contagem de dias em uso | `America/Sao_Paulo` |

O `AMBIENTE` padrão é `desenvolvimento`, que permite o cookie de sessão sem `Secure` e deixa a documentação interativa da API ativa. Nunca versione um `.env` com valores reais.

> **Atenção:** tudo que começa com `VITE_` vai para o JavaScript do navegador e é público. Não coloque segredos em `frontend/.env`.

## 3. Subir o sistema

```bash
docker compose up --build -d
docker compose exec backend python -m alembic upgrade head
```

A segunda linha cria as tabelas. Depois disso:

| Serviço | Endereço |
| --- | --- |
| Frontend | http://localhost:5173 |
| API (documentação interativa) | http://localhost:8000/docs |

Para acompanhar os logs: `docker compose logs -f backend`. Para parar: `docker compose down` (os dados do banco ficam no volume `postgres_data`; `docker compose down -v` apaga tudo).

## 4. Criar o primeiro gerente e entrar

O sistema não tem cadastro aberto. A primeira conta nasce por linha de comando, e só pode existir **um** gerente:

```bash
docker compose exec backend python -m src.cli criar-usuario \
  --email gerente@exemplo.com --nome "Gerente" --papel gerente
```

O comando pede a senha. Ela precisa ter de **8 a 128 caracteres**, com pelo menos uma letra e um número, e não pode ser uma senha comum, uma sequência simples nem derivada do e-mail ou do nome. Para automatizar, use `--senha-stdin` e passe a senha pela entrada padrão.

Abra http://localhost:5173 e entre. Depois, na tela **Contas**, o gerente cria contas de operador com senha inicial, e cada operador troca essa senha no primeiro acesso. Os outros comandos de administração (`definir-papel`, `redefinir-senha`, `desativar-usuario`, `ativar-usuario`, `desbloquear-usuario` e `listar-usuarios`) ficam em `python -m src.cli --help`.

Fluxo para testar:

1. **Nova armadilha:** escolha o modelo no catálogo (StickFly K-45) e marque para criar o refil inicial.
2. **Nova análise:** escolha a armadilha e envie uma foto JPEG ou PNG (até 4 MB e pelo menos 512 px no maior lado).
3. **Painel e detalhe:** veja a saturação, o status, o gráfico de evolução e a previsão de dias.
4. **Troca de refil:** no detalhe da armadilha, registre a troca para começar um novo ciclo.

## 5. Escolher o motor de inferência

| `INFERENCE_MODE` | O que faz | Quando usar |
| --- | --- | --- |
| `stub` | Devolve um resultado simulado, sem modelo | Desenvolver telas e API sem o modelo (padrão do exemplo) |
| `onnx` | Roda a U-Net exportada em ONNX Runtime, em CPU, sem PyTorch | **Produção e demonstração**; é o que está publicado |
| `modelo` | Carrega um checkpoint PyTorch (`.pt`) | Avaliar um treino recente; exige as dependências de inferência com PyTorch |

Para usar o modelo real versionado no repositório (`backend/models/modelo.onnx`), edite o `backend/.env`:

```ini
INFERENCE_MODE=onnx
MODEL_VERSION=v0.1.0-e1
MODEL_WEIGHTS_PATH=
```

e recrie o backend: `docker compose up -d --force-recreate backend`.

Na inicialização, o backend confere o SHA-256 do arquivo, as dimensões de entrada e saída (768 × 576, 3 classes) e se a saída é finita. Se algo não bater, ele **não sobe**. O `MODEL_VERSION` precisa ser igual à versão registrada em `backend/models/modelo.json`, sem o sufixo do hash.

## 6. Desenvolver sem Docker

O banco continua no Docker (`docker compose up -d db`); a API e o frontend rodam na sua máquina.

**Backend** (a partir de `backend/`):

```bash
uv sync --group dev
# exporte DATABASE_URL (com host localhost), MODEL_VERSION, UPLOADS_DIR e CORS_ORIGENS;
# o processo não lê o arquivo .env sozinho
uv run alembic upgrade head
uv run uvicorn src.main:app --reload
```

**Frontend** (a partir de `frontend/`):

```bash
npm ci
npm run dev
```

O frontend usa `VITE_API_URL=http://localhost:8000/api` e funciona com o backend do Docker ou o local.

## 7. Rodar os testes

**Frontend** (lint, tipos e testes):

```bash
cd frontend
npm ci
npm run lint
npm run build
npm test
```

**Backend.** Os testes de integração precisam de um PostgreSQL. Com `docker compose up -d db` ativo, o script cria um banco separado (`armadilhas_test`) dentro dele e roda tudo num contêiner descartável:

```bash
scripts/testar-backend.sh                              # suíte completa
scripts/testar-backend.sh "uv run pytest tests/inference -q"
scripts/testar-backend.sh "uv run ruff check src tests"
```

O script procura o banco no projeto Compose chamado `trapsight-dev`. Se você subiu a pilha com o nome padrão, descubra o nome com `docker compose ls` e informe-o: `PROJETO_COMPOSE=<nome> scripts/testar-backend.sh`.

Alguns testes são pulados quando faltam o PyTorch ou os dados de treino. Isso é esperado fora de uma máquina de treino.

**Não há CI automático.** O GitHub Actions foi desligado em 05/11/2026, porque o projeto tem um só mantenedor. Antes de publicar, rode você mesmo:

- backend: `scripts/testar-backend.sh "uv run ruff check src tests"`, `scripts/testar-backend.sh "uv run ruff format --check src tests"` e `scripts/testar-backend.sh` (testes);
- frontend: `npm run lint`, `npm run build` e `npm test`;
- migrações com o papel de produção: `bash scripts/verificar-migracoes-producao.sh`.

O workflow antigo continua no histórico do Git (por exemplo, no commit da tag `v0.1.0`, em `.github/workflows/ci.yml`) e pode ser restaurado se um dia houver mais pessoas no projeto.

## 8. Dados de demonstração

O seed (`backend/src/seed_demo.py`) cria seis cenários prontos (armadilha para trocar, com projeção, com refil novo, com histórico, sem análises e sem refil ativo). Ele usa fotos geradas a partir do banco de sprites de insetos, que é licenciado e **não faz parte do repositório**. Sem esse catálogo, cadastre armadilhas e envie fotos pela interface, como na seção 4. O procedimento completo do seed está em [`backend/README.md`](../backend/README.md).

## 9. Treinar e exportar o modelo

Tudo parte de `backend/` com o grupo de dependências de treino (PyTorch com CUDA no Windows):

```bash
uv sync --group treino
uv run python -m training.treino gpu          # confere a GPU e a memória de vídeo
```

O treino precisa de duas coisas que ficam **fora do repositório**: o catálogo de sprites (`manifest.json` e PNGs, com autor, fonte e licença de cada um) e o dataset gerado a partir dele. A geração está descrita em [`backend/training/README.md`](../backend/training/README.md) e na especificação [`dataset_sintetico.md`](../.context/plan/data/dataset_sintetico.md).

```bash
# treina e valida (não abre o conjunto de teste)
uv run python -m training.treino treinar \
  --dataset <pasta do dataset> --saida <pasta das execuções> \
  --nome e1 --versao-modelo v0.1.0-e1

# mede o conjunto de teste com o melhor checkpoint
uv run python -m training.treino avaliar-teste --execucao <pasta da execução>

# exporta para ONNX e confere a paridade com o PyTorch
uv run python -m training.exportar_onnx <checkpoint.pt> <dataset> <pasta de destino> \
  --versao v0.1.0-e1
```

Para publicar um modelo novo, copie o `.onnx` e o `.json` gerados para `backend/models/` e ajuste `MODEL_VERSION`. A configuração padrão do treino (função de perda, otimizador, augmentation) está em [`treino_spec.md`](../.context/plan/model/treino_spec.md), e os critérios de aprovação, em [`avaliacao_spec.md`](../.context/plan/model/avaliacao_spec.md).

## 10. Publicar na internet

A publicação usa um único projeto na Vercel (frontend Vite e API FastAPI) e um banco PostgreSQL no Supabase. O passo a passo, com as variáveis de cada ambiente, a homologação descartável (Preview) e as precauções de segurança, está em [`deploy/vercel-supabase.md`](../deploy/vercel-supabase.md). Em resumo:

- a branch `main` publica em **produção**; qualquer outra branch, como a `dev`, gera um **Preview**;
- as migrações rodam com o administrador do banco, e o app com a conta `trapsight_runtime`;
- no Supabase use o pooler de transações (porta `6543`) para o app e o de sessão (`5432`) para migrações.

## 11. Produção local, segurança e backup

- **Compose de produção:** `docker-compose.prod.yml` põe o Caddy na frente (HTTPS automático) e deixa só as portas 80 e 443 públicas. As variáveis ficam em `.env.prod` (modelo em `.env.prod.example`).
- **Testes de segurança:** a suíte em [`security/`](../security/README.md) roda varreduras (OWASP ZAP e Nuclei) e um pentest próprio contra essa pilha local. Os relatórios não são versionados.
- **Backup e restauração:** `scripts/backup-banco.sh`, `scripts/restaurar-banco.sh` e `scripts/testar-restauracao.sh`. O procedimento está em [`deploy/backup-restauracao.md`](../deploy/backup-restauracao.md).

## 12. Problemas comuns

| Sintoma | Causa provável e solução |
| --- | --- |
| `port is already allocated` na `5432` | Já existe um PostgreSQL local. Pare-o ou mude a porta publicada do serviço `db` em `docker-compose.yml`. |
| `Defina POSTGRES_USER no .env da raiz` | O `.env` da raiz não foi criado ou está com os valores vazios. |
| A API não conecta ao banco | A `DATABASE_URL` do `backend/.env` não repete o usuário, a senha e o banco do `.env` da raiz, ou o host não é `db`. |
| Login falha com `403` (`CSRF_INVALIDO`) | A origem do navegador não está em `CORS_ORIGENS`. Em desenvolvimento, use `http://localhost:5173`. |
| `SENHA_FRACA` ao criar a conta | Use 8 caracteres ou mais, com letras e números, sem palavras comuns e sem partes do e-mail ou do nome. |
| O backend não sobe no modo `onnx` | Confira `MODEL_VERSION` (igual à de `backend/models/modelo.json`, sem o hash) e se `backend/models/modelo.onnx` está íntegro. A mensagem de erro diz qual conferência falhou. |
| `PLACA_NAO_DETECTADA` ao analisar | A foto não mostra a placa adesiva com clareza (a placa ocupa menos de 5% da imagem). Fotografe a placa mais de perto e de frente. |
| A primeira análise demora | O modelo roda em CPU, em cerca de 5 segundos por foto, e a primeira chamada após um período parado é mais lenta. |
