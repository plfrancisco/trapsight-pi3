#!/bin/sh
# Cria os papéis de menor privilégio na primeira inicialização do volume.
#   trapsight_migrador: dono do esquema; só ele altera a estrutura (migrations).
#   trapsight_app:      usado pela API; apenas SELECT/INSERT/UPDATE/DELETE.
# Ambos sem SUPERUSER, CREATEDB nem CREATEROLE. Senhas vêm do ambiente.
set -eu

: "${DB_MIGRADOR_SENHA:?DB_MIGRADOR_SENHA não definida}"
: "${DB_APP_SENHA:?DB_APP_SENHA não definida}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
  -v banco="$POSTGRES_DB" \
  -v senha_migrador="$DB_MIGRADOR_SENHA" \
  -v senha_app="$DB_APP_SENHA" <<'SQL'
CREATE ROLE trapsight_migrador LOGIN PASSWORD :'senha_migrador'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
CREATE ROLE trapsight_app LOGIN PASSWORD :'senha_app'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;

ALTER DATABASE :"banco" OWNER TO trapsight_migrador;
REVOKE CONNECT ON DATABASE :"banco" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"banco" TO trapsight_migrador, trapsight_app;

\connect :"banco"

ALTER SCHEMA public OWNER TO trapsight_migrador;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO trapsight_app;

ALTER DEFAULT PRIVILEGES FOR ROLE trapsight_migrador IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO trapsight_app;
ALTER DEFAULT PRIVILEGES FOR ROLE trapsight_migrador IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO trapsight_app;
SQL
