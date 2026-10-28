#!/usr/bin/env bash
# Restaura em um banco vazio uma cópia gerada por scripts/backup-banco.sh.
#
# Recusa rodar contra um banco que já tenha dados: restaurar por cima de tabelas
# existentes mistura dois estados e produz um banco que não corresponde a nenhum
# dos dois. O arquivo é decifrado em memória e vai direto para o pg_restore, sem
# que o dump em claro toque o disco. Quando existe o `.sha256` ao lado, ele é
# conferido antes de qualquer escrita.
#
# Variáveis de ambiente:
#   RESTORE_DATABASE_URL    conexão do banco de destino; o padrão é DATABASE_URL
#   RESTORE_CHAVE_PRIVADA   chave privada do CMS, sempre fora do repositório
#                           (padrão: ~/.trapsight-seguranca/chave_privada.pem)
#   RESTORE_DOCKER_REDE     rede docker em que o banco responde, quando o
#                           pg_restore roda em contêiner
#   RESTORE_IMAGEM_PG       imagem com pg_restore e psql, usada quando não estão
#                           no PATH (padrão: postgres:17.6-alpine)
#
# Uso (na raiz do repositório):
#   RESTORE_DATABASE_URL=... scripts/restaurar-banco.sh <arquivo.dump.cms>
set -euo pipefail
umask 077
export MSYS_NO_PATHCONV=1

IMAGEM_PG="${RESTORE_IMAGEM_PG:-postgres:17.6-alpine}"
REDE="${RESTORE_DOCKER_REDE:-}"

# O openssl nativo do Windows não entende caminhos /c/...; o cygpath os converte.
winpath() { cygpath -m "$1" 2>/dev/null || echo "$1"; }

hash_sha256() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    openssl dgst -sha256 "$(winpath "$1")" | awk '{print $NF}'
  fi
}

ARQUIVO="${1:-}"
if [ -z "$ARQUIVO" ]; then
  echo "Informe o arquivo de backup. Uso: scripts/restaurar-banco.sh <arquivo.dump.cms>" >&2
  exit 64
fi
[ -f "$ARQUIVO" ] || { echo "Arquivo não encontrado: $ARQUIVO" >&2; exit 66; }

URL="${RESTORE_DATABASE_URL:-${DATABASE_URL:-}}"
if [ -z "$URL" ]; then
  echo "Defina RESTORE_DATABASE_URL (ou DATABASE_URL) com o banco de destino." >&2
  exit 64
fi

if [[ "$URL" =~ ^([a-z]+)\+[a-z0-9]+(://.*)$ ]]; then
  URL="${BASH_REMATCH[1]}${BASH_REMATCH[2]}"
fi

if [[ "$URL" =~ ^([a-z]+://[^:/?#@]+):([^@]*)@(.*)$ ]]; then
  SENHA="${BASH_REMATCH[2]}"
  URL="${BASH_REMATCH[1]}@${BASH_REMATCH[3]}"
  case "$SENHA" in
    *%*) SENHA="$(printf '%b' "${SENHA//%/\x}")" ;;
  esac
  [ -n "$SENHA" ] && export PGPASSWORD="$SENHA"
  unset SENHA
fi

case "$ARQUIVO" in
  *.gpg)
    command -v gpg >/dev/null 2>&1 || { echo "gpg não encontrado." >&2; exit 66; }
    decifrar() { gpg --batch --quiet --decrypt "$ARQUIVO"; }
    ;;
  *.cms)
    command -v openssl >/dev/null 2>&1 || { echo "openssl não encontrado." >&2; exit 66; }
    CHAVE="${RESTORE_CHAVE_PRIVADA:-$HOME/.trapsight-seguranca/chave_privada.pem}"
    [ -f "$CHAVE" ] || { echo "Chave privada não encontrada em $CHAVE" >&2; exit 66; }
    decifrar() {
      openssl cms -decrypt -binary -inform DER \
        -in "$(winpath "$ARQUIVO")" -inkey "$(winpath "$CHAVE")"
    }
    ;;
  *)
    echo "Extensão não reconhecida: use um arquivo .dump.cms ou .dump.gpg." >&2
    exit 64
    ;;
esac

executar_pg() {
  local programa="$1"
  shift
  if command -v "$programa" >/dev/null 2>&1; then
    "$programa" "$@"
  else
    # shellcheck disable=SC2086 # --network só entra quando a rede é informada
    docker run --rm -i ${REDE:+--network "$REDE"} -e PGPASSWORD "$IMAGEM_PG" \
      "$programa" "$@"
  fi
}

ERROS="$(mktemp)"
chmod 600 "$ERROS"
trap 'rm -f "$ERROS"' EXIT
falhar() {
  sed -E 's#[a-z]+://[^[:space:]]+#<conexão omitida>#g' "$ERROS" >&2
  echo "$1" >&2
  exit 70
}

HASH_ESPERADO=""
if [ -f "$ARQUIVO.sha256" ]; then
  HASH_ESPERADO="$(awk '{print $1}' "$ARQUIVO.sha256")"
  HASH_ATUAL="$(hash_sha256 "$ARQUIVO")"
  if [ "$HASH_ATUAL" != "$HASH_ESPERADO" ]; then
    echo "O SHA-256 do arquivo não corresponde ao registrado; restauração abortada." >&2
    exit 65
  fi
  echo "SHA-256 conferido: $HASH_ATUAL"
else
  echo "Aviso: não há $(basename "$ARQUIVO").sha256; a integridade não foi conferida." >&2
fi

# Só o schema `public` é avaliado: num banco gerenciado como o Supabase, os
# schemas da plataforma (auth, storage, extensions) sempre têm tabelas, e exigir
# o cluster inteiro vazio impediria qualquer restauração.
TABELAS="$(executar_pg psql --dbname="$URL" -tAq -v ON_ERROR_STOP=1 -c "
  SELECT count(*) FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
   WHERE c.relkind IN ('r', 'p') AND n.nspname = 'public'" 2>"$ERROS" | tr -d '[:space:]')" \
  || falhar "Não foi possível consultar o banco de destino."
if [ -z "$TABELAS" ]; then
  falhar "O banco de destino não respondeu à consulta de verificação."
fi
if [ "$TABELAS" != "0" ]; then
  echo "O banco de destino já tem $TABELAS tabela(s) no schema public." >&2
  echo "A restauração só roda em banco vazio: crie um banco novo e repita." >&2
  exit 65
fi

if ! decifrar 2>"$ERROS" | executar_pg pg_restore --dbname="$URL" \
  --single-transaction --exit-on-error 2>>"$ERROS"; then
  falhar "Falha ao restaurar; a transação única garante que nada foi aplicado."
fi

echo "Restauração concluída em um banco que estava vazio."
