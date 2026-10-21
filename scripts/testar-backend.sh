#!/usr/bin/env bash
# Roda comandos do backend usando o banco da pilha de desenvolvimento.
#
# Não sobe PostgreSQL próprio: cria o banco `armadilhas_test` dentro do contêiner
# `db` que já está ativo e executa o comando em um contêiner descartável (--rm)
# ligado à mesma rede. Os testes ficam isolados do banco de desenvolvimento.
#
# Uso (na raiz do repositório, com `docker compose up -d db` ativo):
#   scripts/testar-backend.sh                    # pytest completo
#   scripts/testar-backend.sh "uv run pytest tests/training -q"
#   scripts/testar-backend.sh "uv run ruff check src tests"
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"

BANCO_TESTE="armadilhas_test"
COMANDO="${1:-uv run pytest -q}"

lerEnv() { grep -E "^$1=" .env | head -n1 | cut -d= -f2-; }
USUARIO="$(lerEnv POSTGRES_USER)"
SENHA="$(lerEnv POSTGRES_PASSWORD)"
if [ -z "$USUARIO" ] || [ -z "$SENHA" ]; then
  echo "Defina POSTGRES_USER e POSTGRES_PASSWORD no .env da raiz." >&2
  exit 1
fi

# A pilha pode ter sido iniciada com o nome padrão da pasta ou com `-p trapsight-dev`.
CONTEINER_DB="$(docker compose -p "${PROJETO_COMPOSE:-trapsight-dev}" ps -q db)"
if [ -z "$CONTEINER_DB" ]; then
  CONTEINER_DB="$(docker compose ps -q db)"
fi
if [ -z "$CONTEINER_DB" ]; then
  echo "O banco de desenvolvimento não está ativo. Rode: docker compose up -d db" >&2
  exit 1
fi
REDE="$(docker inspect -f '{{range $nome, $_ := .NetworkSettings.Networks}}{{$nome}}{{end}}' "$CONTEINER_DB")"

existe="$(docker exec "$CONTEINER_DB" psql -U "$USUARIO" -d postgres -tAc \
  "SELECT 1 FROM pg_database WHERE datname = '$BANCO_TESTE'")"
if [ "$existe" != "1" ]; then
  docker exec "$CONTEINER_DB" createdb -U "$USUARIO" "$BANCO_TESTE"
fi

MSYS_NO_PATHCONV=1 docker run --rm --network "$REDE" \
  -v "$RAIZ/backend:/b" -v "$RAIZ/security:/security:ro" -v uvcache:/root/.cache/uv \
  -w /b \
  -e UV_PROJECT_ENVIRONMENT=/tmp/venv -e PYTHONPATH=/b \
  -e DATABASE_URL="postgresql://$USUARIO:$SENHA@db:5432/$BANCO_TESTE" \
  -e MODEL_WEIGHTS_PATH=/tmp/pesos.pt -e MODEL_VERSION=v0.1.0-dev \
  -e UPLOADS_DIR=/tmp/uploads -e CORS_ORIGENS=http://localhost:5173 \
  ghcr.io/astral-sh/uv:python3.12-bookworm-slim \
  sh -c "uv sync --quiet --locked >/dev/null 2>&1; uv run --quiet alembic upgrade head; $COMANDO"
