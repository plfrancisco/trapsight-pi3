#!/usr/bin/env bash
# Abre um relatório cifrado por executar_cego.sh.
# USO RESTRITO ao revisor/dono da chave privada. Quem implementa o sistema NÃO deve executar este script.
#
# Uso:   bash security/scans/abrir_relatorio.sh <arquivo.cms> [pasta_de_saida]
# A chave privada fica FORA do repositório (padrão: ~/.trapsight-seguranca/chave_privada.pem).
# Variável opcional: SEC_CHAVE_PRIVADA (caminho da chave).
# O texto claro é gravado FORA do repositório (padrão: ~/.trapsight-seguranca/relatorios/<nome>/).

set -eu
winpath() { cygpath -m "$1" 2>/dev/null || echo "$1"; }
ARQ="${1:?Informe o arquivo .cms}"
CHAVE="${SEC_CHAVE_PRIVADA:-$HOME/.trapsight-seguranca/chave_privada.pem}"
NOME="$(basename "$ARQ" .cms)"
DEST="${2:-$HOME/.trapsight-seguranca/relatorios/$NOME}"
[ -f "$CHAVE" ] || { echo "Chave privada não encontrada em $CHAVE"; exit 66; }
mkdir -p "$DEST"
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT
openssl cms -decrypt -binary -in "$(winpath "$ARQ")" -inform DER -inkey "$(winpath "$CHAVE")" -out "$(winpath "$TMP")"
tar -C "$DEST" -xf "$TMP"
echo "Relatório aberto em: $DEST"
