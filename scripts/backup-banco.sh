#!/usr/bin/env bash
# Gera uma cópia cifrada do PostgreSQL em um diretório fora do repositório.
#
# A conexão vem só do ambiente e nunca chega à saída: a mensagem de erro do
# pg_dump passa por um filtro que apaga qualquer URL antes de ser impressa, e a
# senha é movida da URL para PGPASSWORD, de modo que não apareça na linha de
# comando (visível a qualquer processo da máquina). O dump sai no formato custom
# do pg_dump, que o pg_restore aplica seletivamente, e é cifrado para uma chave
# pública — a privada fica fora do repositório. O arquivo `.sha256` registra o
# hash do artefato cifrado, que permite conferir a integridade de uma cópia
# arquivada sem precisar decifrá-la.
#
# Variáveis de ambiente:
#   BACKUP_DATABASE_URL     conexão do banco a copiar; o padrão é DATABASE_URL
#   BACKUP_DIR              diretório de saída, sempre fora do repositório
#                           (padrão: ~/backups-trapsight)
#   BACKUP_CERTIFICADO      certificado público usado por `openssl cms`
#                           (padrão: security/cifra/certificado.pem)
#   BACKUP_GPG_DESTINATARIO cifra com gpg para essa chave pública, em vez do CMS
#   BACKUP_DOCKER_REDE      rede docker em que o banco responde, quando o
#                           pg_dump roda em contêiner
#   BACKUP_IMAGEM_PG        imagem com o pg_dump, usada quando ele não está no
#                           PATH (padrão: postgres:17.6-alpine)
#
# Uso (na raiz do repositório):
#   BACKUP_DATABASE_URL=... scripts/backup-banco.sh
set -euo pipefail
umask 077
export MSYS_NO_PATHCONV=1

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGEM_PG="${BACKUP_IMAGEM_PG:-postgres:17.6-alpine}"
REDE="${BACKUP_DOCKER_REDE:-}"

# O openssl nativo do Windows não entende caminhos /c/...; o cygpath os converte.
winpath() { cygpath -m "$1" 2>/dev/null || echo "$1"; }

hash_sha256() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    openssl dgst -sha256 "$(winpath "$1")" | awk '{print $NF}'
  fi
}

URL="${BACKUP_DATABASE_URL:-${DATABASE_URL:-}}"
if [ -z "$URL" ]; then
  echo "Defina BACKUP_DATABASE_URL (ou DATABASE_URL) com a conexão do banco." >&2
  exit 64
fi

# A aplicação usa a URL no dialeto do SQLAlchemy (postgresql+psycopg://), que o
# pg_dump não aceita; o nome do driver é descartado.
if [[ "$URL" =~ ^([a-z]+)\+[a-z0-9]+(://.*)$ ]]; then
  URL="${BASH_REMATCH[1]}${BASH_REMATCH[2]}"
fi

if [[ "$URL" =~ ^([a-z]+://[^:/?#@]+):([^@]*)@(.*)$ ]]; then
  SENHA="${BASH_REMATCH[2]}"
  URL="${BASH_REMATCH[1]}@${BASH_REMATCH[3]}"
  # Caracteres reservados chegam percent-encoded na URL e precisam voltar ao
  # original antes de ir para a variável que o libpq lê.
  case "$SENHA" in
    *%*) SENHA="$(printf '%b' "${SENHA//%/\x}")" ;;
  esac
  [ -n "$SENHA" ] && export PGPASSWORD="$SENHA"
  unset SENHA
fi

if [ -n "${BACKUP_GPG_DESTINATARIO:-}" ]; then
  SUFIXO="gpg"
  command -v gpg >/dev/null 2>&1 || {
    echo "gpg não encontrado, mas BACKUP_GPG_DESTINATARIO está definido." >&2
    exit 66
  }
else
  SUFIXO="cms"
  CERTIFICADO="${BACKUP_CERTIFICADO:-$RAIZ/security/cifra/certificado.pem}"
  command -v openssl >/dev/null 2>&1 || { echo "openssl não encontrado." >&2; exit 66; }
  [ -f "$CERTIFICADO" ] || {
    echo "Certificado público ausente: $CERTIFICADO" >&2
    exit 66
  }
fi

cifrar() {
  case "$SUFIXO" in
    gpg)
      gpg --batch --yes --quiet --trust-model always \
        --encrypt --recipient "$BACKUP_GPG_DESTINATARIO" --output -
      ;;
    cms)
      openssl cms -encrypt -aes256 -binary -outform DER "$(winpath "$CERTIFICADO")"
      ;;
  esac
}

despejar() {
  # O dump sai completo, com donos e permissões: o banco de destino precisa ter
  # os papéis que as migrações criam (trapsight_backend, trapsight_runtime).
  if command -v pg_dump >/dev/null 2>&1; then
    pg_dump --format=custom --dbname="$URL"
  else
    # shellcheck disable=SC2086 # --network só entra quando a rede é informada
    docker run --rm ${REDE:+--network "$REDE"} -e PGPASSWORD "$IMAGEM_PG" \
      pg_dump --format=custom --dbname="$URL"
  fi
}

DESTINO="${BACKUP_DIR:-$HOME/backups-trapsight}"
mkdir -p "$DESTINO"
DESTINO="$(cd "$DESTINO" && pwd)"
# Um dump dentro da árvore do projeto corre o risco de ser commitado ou servido
# pelo proxy; o diretório de saída precisa estar fora dela.
case "$DESTINO/" in
  "$RAIZ"/*)
    echo "BACKUP_DIR não pode ficar dentro do repositório: $DESTINO" >&2
    exit 64
    ;;
esac
chmod 700 "$DESTINO"

ARQUIVO="$DESTINO/armadilhas-$(date -u +%Y%m%dT%H%M%SZ).dump.$SUFIXO"
PARCIAL="$ARQUIVO.parcial"
ERROS="$(mktemp)"
chmod 600 "$ERROS"
trap 'rm -f "$ERROS" "$PARCIAL"' EXIT

if ! { despejar 2>"$ERROS" | cifrar 2>>"$ERROS"; } > "$PARCIAL"; then
  sed -E 's#[a-z]+://[^[:space:]]+#<conexão omitida>#g' "$ERROS" >&2
  echo "Falha ao gerar o backup; nenhum arquivo foi mantido." >&2
  exit 70
fi
if [ ! -s "$PARCIAL" ]; then
  echo "O dump saiu vazio; nenhum arquivo foi mantido." >&2
  exit 70
fi

TAMANHO="$(wc -c < "$PARCIAL" | tr -d ' ')"
HASH="$(hash_sha256 "$PARCIAL")"
mv "$PARCIAL" "$ARQUIVO"
printf '%s  %s\n' "$HASH" "$(basename "$ARQUIVO")" > "$ARQUIVO.sha256"
chmod 600 "$ARQUIVO" "$ARQUIVO.sha256"

echo "Backup cifrado: $ARQUIVO"
echo "Tamanho: $TAMANHO bytes"
echo "SHA-256: $HASH"
echo "O conteúdo só abre com a chave privada, que fica fora do repositório."
