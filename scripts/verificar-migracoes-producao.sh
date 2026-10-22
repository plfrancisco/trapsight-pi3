#!/usr/bin/env bash
# Confirma que as migrações rodam com o papel de migração do Compose de produção.
#
# Esse papel (trapsight_migrador) não tem CREATEROLE, então migrações que criam
# papéis precisam se omitir nele. O script sobe um PostgreSQL descartável com os
# mesmos papéis de deploy/db/init/01-papeis.sh, aplica `alembic upgrade head`,
# desce até a 0006 e sobe de novo. Falha se qualquer passo falhar.
#
# Uso (na raiz do repositório, com o Docker ativo):
#   scripts/verificar-migracoes-producao.sh
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"

REDE="pi-migracoes-prod"
BANCO="pi-migracoes-prod-db"
gerar() { head -c 40 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 20; }
SENHA_ADMIN="$(gerar)"; SENHA_MIGRADOR="$(gerar)"; SENHA_APP="$(gerar)"

limpar() {
  docker rm -f "$BANCO" >/dev/null 2>&1 || true
  docker network rm "$REDE" >/dev/null 2>&1 || true
}
trap limpar EXIT
limpar
docker network create "$REDE" >/dev/null

docker run -d --name "$BANCO" --network "$REDE" \
  -e POSTGRES_USER=root -e POSTGRES_PASSWORD="$SENHA_ADMIN" -e POSTGRES_DB=armadilhas \
  postgres:17.6-alpine >/dev/null
# A imagem oficial sobe um servidor temporário para a inicialização e depois
# reinicia; só o segundo "ready" indica o servidor definitivo.
for _ in $(seq 1 60); do
  [ "$(docker logs "$BANCO" 2>&1 | grep -c 'ready to accept connections')" -ge 2 ] && break
  sleep 1
done

docker exec -i "$BANCO" psql -U root -d postgres -v ON_ERROR_STOP=1 -q <<SQL
CREATE ROLE trapsight_migrador LOGIN PASSWORD '$SENHA_MIGRADOR'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
CREATE ROLE trapsight_app LOGIN PASSWORD '$SENHA_APP'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
ALTER DATABASE armadilhas OWNER TO trapsight_migrador;
\connect armadilhas
ALTER SCHEMA public OWNER TO trapsight_migrador;
GRANT USAGE ON SCHEMA public TO trapsight_app;
ALTER DEFAULT PRIVILEGES FOR ROLE trapsight_migrador IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO trapsight_app;
SQL

MSYS_NO_PATHCONV=1 docker run --rm --network "$REDE" \
  -v "$RAIZ/backend:/b" -v uvcache:/root/.cache/uv -w /b \
  -e UV_PROJECT_ENVIRONMENT=/tmp/venv -e PYTHONPATH=/b \
  -e DATABASE_URL="postgresql://trapsight_migrador:$SENHA_MIGRADOR@$BANCO:5432/armadilhas" \
  -e MODEL_WEIGHTS_PATH=/tmp/pesos.pt -e MODEL_VERSION=v0.1.0-dev \
  -e UPLOADS_DIR=/tmp/uploads -e CORS_ORIGENS=http://localhost:5173 \
  ghcr.io/astral-sh/uv:python3.12-bookworm-slim \
  sh -c "uv sync --quiet --locked >/dev/null 2>&1 \
    && uv run --quiet alembic upgrade head \
    && uv run --quiet alembic downgrade 0006 \
    && uv run --quiet alembic upgrade head"

versao="$(docker exec "$BANCO" psql -U root -d armadilhas -tAc 'select version_num from alembic_version')"
echo "Migrações aplicadas com o papel do Compose de produção; versão $versao."
