#!/usr/bin/env bash
# Executor CEGO das varreduras de segurança.
#
# Quem implementa o sistema (Codex) só EXECUTA: este script roda os modos pedidos,
# CIFRA o relatório completo com a chave pública do projeto e apaga o texto claro.
# Na saída aparece apenas se a execução aconteceu, nunca o que foi encontrado.
# Só o dono da chave privada (fora do repositório) consegue abrir o relatório,
# com security/scans/abrir_relatorio.sh.
#
# Uso:   bash security/scans/executar_cego.sh <modo> [<modo> ...]
#        (modos de run_scans.sh: codigo | rede | passivo | pentest | ativo | tudo)
# Mesmas variáveis de run_scans.sh (TARGET_URL, DOCKER_NET, SEC_*, PASSADA, PYTEST_ARGS...).
#
# Regras para quem executa:
#  - NÃO leia security/reports/ (só haverá um arquivo .cms, ilegível sem a chave).
#  - NÃO procure, copie nem use a chave privada.
#  - NÃO use logs dos contêineres alvo para descobrir resultados dos testes.
#  - NÃO altere os testes nem os scripts para "melhorar" o resultado.

set -u
export MSYS_NO_PATHCONV=1
# openssl nativo do Windows não entende /c/...: converte para D:/... quando houver cygpath
winpath() { cygpath -m "$1" 2>/dev/null || echo "$1"; }
REPO="$(cd "$(dirname "$0")/../.." && (pwd -W 2>/dev/null || pwd))"
CERT="$REPO/security/cifra/certificado.pem"
COMMIT="$(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo semgit)"
[ "$#" -ge 1 ] || { echo "Informe ao menos um modo. Ex.: bash security/scans/executar_cego.sh codigo pentest"; exit 64; }
[ -f "$CERT" ] || { echo "ERRO: falta $CERT (certificado público do projeto). Nada foi executado."; exit 66; }
command -v openssl >/dev/null || { echo "ERRO: openssl não encontrado. Nada foi executado."; exit 66; }

MODOS="$*"
ROTULO="$(date +%F_%H%M%S)_${COMMIT}_${MODOS// /-}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$REPO/security/reports"

for modo in "$@"; do
  RELATORIO_DIR="$TMP/$modo" SILENCIOSO=1 bash "$REPO/security/scans/run_scans.sh" "$modo" >/dev/null 2>&1
done

# Só informações de INFRAESTRUTURA vão para a tela: quais etapas não puderam rodar e por quê.
# Resultados (aprovado, reprovado, avisos, contagens) nunca são mostrados.
TOTAL=0; NAO_EXEC=()
while IFS= read -r linha; do
  TOTAL=$((TOTAL + 1))
  case "$linha" in
    *NAO_EXECUTADO*) NAO_EXEC+=("${linha%% *}: ${linha#*NAO_EXECUTADO }") ;;
  esac
done < <(cat "$TMP"/*/RESUMO.txt 2>/dev/null)

ARQ="$REPO/security/reports/relatorio_${ROTULO}.cms"
tar -C "$TMP" -cf "$TMP/relatorio.tar" . 2>/dev/null
if openssl cms -encrypt -aes256 -binary -in "$(winpath "$TMP/relatorio.tar")" -out "$(winpath "$ARQ")" -outform DER "$(winpath "$CERT")" 2>/dev/null; then
  HASH="$(openssl dgst -sha256 "$(winpath "$ARQ")" | awk '{print $NF}')"
  echo "Execução concluída: modos [$MODOS], $TOTAL etapa(s) registradas."
  if [ "${#NAO_EXEC[@]}" -gt 0 ]; then
    echo "Etapas que NÃO puderam ser executadas (problema de ambiente, corrigir e repetir):"
    printf '  - %s\n' "${NAO_EXEC[@]}"
  fi
  echo "Relatório cifrado: security/reports/$(basename "$ARQ")"
  echo "SHA-256: $HASH"
  echo "O conteúdo só pode ser aberto por quem tem a chave privada. Envie o arquivo ao revisor."
else
  echo "ERRO: não foi possível cifrar o relatório; nada foi gravado em claro."
  exit 70
fi
exit 0
