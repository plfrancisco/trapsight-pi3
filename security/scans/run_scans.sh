#!/usr/bin/env bash
# Orquestra as varreduras de segurança do TrapSight em contêineres.
#
# Uso:   bash security/scans/run_scans.sh <modo>
# Modos: codigo      segredos, dependências, SAST, imagens e Dockerfiles (sem alvo)
#        rede        nmap (todas as portas) e testssl.sh        [exige TARGET_HOST]
#        passivo     ZAP baseline e Nuclei sem ataque           [exige TARGET_URL]
#        pentest     suíte caixa-preta (pytest)                 [exige TARGET_URL]
#        ativo       ZAP API/full, Nuclei ativo e sqlmap        [SOMENTE homologação]
#        tudo        codigo + rede + passivo + pentest
#
# Variáveis: TARGET_URL, TARGET_HOST, DOCKER_NET (rede do Compose, opcional),
#            SEC_* (credenciais de teste, só homologação), CONFIRMO_HOMOLOGACAO=sim
#
# Regras (security/README.md e .context/validation/seguranca_testes.md):
#  - NUNCA apontar para sistemas de terceiros.
#  - O modo "ativo" ataca de verdade: só em homologação descartável.
#  - Nenhuma credencial é impressa nem gravada em relatório.

set -u
MODO="${1:-}"
export MSYS_NO_PATHCONV=1   # Git Bash no Windows: não converter caminhos de volume

REPO="$(cd "$(dirname "$0")/../.." && (pwd -W 2>/dev/null || pwd))"
COMMIT="$(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo semgit)"
# RELATORIO_DIR e SILENCIOSO são usados pelo executor cego (executar_cego.sh): o relatório
# vai para um diretório temporário e nada sobre os resultados é impresso.
OUT="${RELATORIO_DIR:-$REPO/security/reports/$(date +%F)_${COMMIT}_${MODO}}"
mkdir -p "$OUT"
RESUMO="$OUT/RESUMO.txt"
: >> "$RESUMO"
NET_ARGS=()
[ -n "${DOCKER_NET:-}" ] && NET_ARGS=(--network "$DOCKER_NET")

# registra "etapa | resultado" no resumo (no modo silencioso, apenas grava)
registrar() {
  if [ "${SILENCIOSO:-0}" = "1" ]; then
    printf '%-28s %s\n' "$1" "$2" >> "$RESUMO"
  else
    printf '%-28s %s\n' "$1" "$2" | tee -a "$RESUMO"
  fi
}

# garante a imagem e grava o digest (evidência reproduzível)
preparar() {
  # imagem só local (ex.: SEC_IMAGEM) é aceita quando não há como baixá-la
  if ! docker pull -q "$1" >/dev/null 2>&1 && ! docker image inspect "$1" >/dev/null 2>&1; then return 1; fi
  docker image inspect --format '{{index .RepoDigests 0}}' "$1" 2>/dev/null >> "$OUT/imagens.txt" || echo "$1 (sem digest)" >> "$OUT/imagens.txt"
}

# executa uma etapa: rodar <nome> <imagem> <comando...>; o código de saída decide
# 0 = APROVADO, 2 = ATENCAO (avisos), demais = REPROVADO; falha de imagem = NAO_EXECUTADO
rodar() {
  local nome="$1" imagem="$2"; shift 2
  if ! preparar "$imagem"; then registrar "$nome" "NAO_EXECUTADO (imagem $imagem indisponível)"; return; fi
  docker run --rm ${NET_ARGS[@]+"${NET_ARGS[@]}"} "$@" > "$OUT/$nome.txt" 2>&1
  local rc=$?
  case $rc in
    0) registrar "$nome" "APROVADO" ;;
    2) registrar "$nome" "ATENCAO (avisos; ver $nome.txt)" ;;
    125|126|127) registrar "$nome" "NAO_EXECUTADO (erro do Docker, código $rc)" ;;
    *) registrar "$nome" "REPROVADO (código $rc; ver $nome.txt)" ;;
  esac
}

codigo() {
  rodar gitleaks ghcr.io/gitleaks/gitleaks:latest \
    -v "$REPO:/repo:ro" ghcr.io/gitleaks/gitleaks:latest detect --source /repo --log-opts="--all" --redact --no-banner
  rodar trivy-fs aquasec/trivy:latest \
    -v "$REPO:/repo:ro" aquasec/trivy:latest fs --scanners vuln,secret,misconfig --severity HIGH,CRITICAL \
    --exit-code 1 --skip-dirs /repo/frontend/node_modules --skip-dirs /repo/.git /repo
  rodar trivy-dockerfiles aquasec/trivy:latest \
    -v "$REPO:/repo:ro" aquasec/trivy:latest config --severity HIGH,CRITICAL --exit-code 1 \
    --skip-dirs /repo/frontend/node_modules --skip-dirs /repo/.git /repo
  # Imagens de produção (docker compose -f docker-compose.prod.yml build); o prefixo é o
  # nome do projeto do Compose (COMPOSE_PROJECT_NAME ou o nome da pasta, sem espaços).
  local projeto="${COMPOSE_PROJECT_NAME:-projetointegrador}"
  for svc in backend proxy; do
    if docker image inspect "$projeto-$svc" >/dev/null 2>&1; then
      docker save -o "$OUT/$svc.tar" "$projeto-$svc"
      rodar "trivy-imagem-$svc" aquasec/trivy:latest \
        -v "$OUT:/out" aquasec/trivy:latest image --input "/out/$svc.tar" --severity HIGH,CRITICAL --exit-code 1
      rm -f "$OUT/$svc.tar"
    else
      registrar "trivy-imagem-$svc" "NAO_EXECUTADO (imagem $projeto-$svc não existe; rode docker compose -f docker-compose.prod.yml build)"
    fi
  done
  for df in backend/Dockerfile deploy/proxy/Dockerfile security/Dockerfile; do
    rodar "hadolint-$(echo "$df" | tr '/' '-')" hadolint/hadolint:latest -v "$REPO/$df:/Dockerfile:ro" hadolint/hadolint:latest hadolint /Dockerfile
  done
  rodar pip-audit python:3.12-slim -v "$REPO/backend:/b:ro" python:3.12-slim \
    sh -c "pip install -q pip-audit && pip-audit -r /b/requirements.txt"
  rodar npm-audit node:24 -v "$REPO/frontend:/f:ro" node:24 \
    sh -c "cp -r /f /tmp/f && cd /tmp/f && npm audit --omit=dev --audit-level=high"
  rodar semgrep semgrep/semgrep:latest -v "$REPO:/src:ro" semgrep/semgrep:latest \
    semgrep --metrics=off --error --severity ERROR --config p/owasp-top-ten --config p/python --config p/typescript \
    /src/backend/src /src/frontend/src
  rodar bandit python:3.12-slim -v "$REPO/backend:/b:ro" python:3.12-slim \
    sh -c "pip install -q bandit && bandit -r /b/src -ll"
}

rede() {
  [ -z "${TARGET_HOST:-}" ] && { registrar rede "NAO_EXECUTADO (defina TARGET_HOST)"; return; }
  # varredura de TODAS as portas TCP: só 80 e 443 podem aparecer abertas
  rodar nmap instrumentisto/nmap:latest instrumentisto/nmap:latest -p- -sV -Pn --open -T4 "$TARGET_HOST"
  if [[ "${TARGET_URL:-}" == https://* ]]; then
    rodar testssl drwetter/testssl.sh:latest drwetter/testssl.sh:latest --severity MEDIUM --quiet --color 0 "$TARGET_URL"
  fi
  # o nmap sempre sai com 0: a interpretação das portas é feita aqui
  if grep -E '^[0-9]+/tcp +open' "$OUT/nmap.txt" 2>/dev/null | grep -Ev '^(80|443)/tcp' | grep -q .; then
    registrar nmap-portas "REPROVADO (portas abertas além de 80/443; ver nmap.txt)"
  elif [ -s "$OUT/nmap.txt" ]; then
    registrar nmap-portas "APROVADO (somente 80/443, ou nenhuma)"
  fi
}

passivo() {
  [ -z "${TARGET_URL:-}" ] && { registrar passivo "NAO_EXECUTADO (defina TARGET_URL)"; return; }
  rodar zap-baseline ghcr.io/zaproxy/zaproxy:stable -v "$OUT:/zap/wrk:rw" ghcr.io/zaproxy/zaproxy:stable \
    zap-baseline.py -t "$TARGET_URL" -r zap-baseline.html -J zap-baseline.json
  rodar nuclei-passivo projectdiscovery/nuclei:latest projectdiscovery/nuclei:latest \
    -u "$TARGET_URL" -tags exposure,misconfig,tech -severity low,medium,high,critical -silent -nc
}

pentest() {
  [ -z "${TARGET_URL:-}" ] && { registrar pentest "NAO_EXECUTADO (defina TARGET_URL)"; return; }
  local envs=(-e TARGET_URL -e TARGET_HOST -e API_PREFIX -e EXPECTED_OPEN_PORTS -e SEC_RUN_RATE_LIMIT
    -e SEC_USER_EMAIL -e SEC_USER_PASSWORD -e SEC_MANAGER_EMAIL -e SEC_MANAGER_PASSWORD
    -e SEC_LOCKOUT_EMAIL -e SEC_LOCKOUT_PASSWORD -e SEC_LOCKOUT_THRESHOLD
    -e SEC_CHANGEPWD_EMAIL -e SEC_CHANGEPWD_PASSWORD -e SEC_CHANGEPWD_NEW -e SEC_MAX_SESSIONS
    -e SEC_IDLE_TIMEOUT_SECONDS -e SEC_ABSOLUTE_TIMEOUT_SECONDS -e PYTEST_ARGS
    -e SEC_DB_DSN_APP -e SEC_DB_DSN_ADMIN)
  # PASSADA (1, 2, 3) nomeia o relatório; PYTEST_ARGS seleciona testes (ex.: -k expiracao)
  # CA extra (somente ambiente local com certificado interno): montada no executor.
  local ca=()
  if [ -n "${SEC_CA_FILE:-}" ]; then ca=(-v "$SEC_CA_FILE:/ca.pem:ro" -e SEC_CA_FILE=/ca.pem); fi
  # SEC_IMAGEM: imagem com as dependências já instaladas (docker build -t <nome> security),
  # necessária quando o executor roda numa rede sem internet.
  local imagem="${SEC_IMAGEM:-python:3.12-slim}" instalar="pip install -q -r /sec/requirements.txt && "
  [ -n "${SEC_IMAGEM:-}" ] && instalar=""
  rodar "pentest-${PASSADA:-1}" "$imagem" "${envs[@]}" ${ca[@]+"${ca[@]}"} -v "$REPO/security:/sec:ro" -v "$OUT:/out:rw" "$imagem" \
    sh -c "${instalar}cd /sec && eval python -m pytest -p no:cacheprovider -rs --junitxml=/out/pentest-${PASSADA:-1}.xml \$PYTEST_ARGS"
}

ativo() {
  if [ "${CONFIRMO_HOMOLOGACAO:-}" != "sim" ]; then
    registrar ativo "NAO_EXECUTADO (ataque ativo exige CONFIRMO_HOMOLOGACAO=sim e alvo de homologação)"; return
  fi
  [ -z "${TARGET_URL:-}" ] && { registrar ativo "NAO_EXECUTADO (defina TARGET_URL)"; return; }
  # 1) OpenAPI gerado offline a partir do código (em produção /openapi.json é fechado)
  if docker image inspect projeto-integrador-backend >/dev/null 2>&1 && [ -f "$REPO/backend/.env" ]; then
    docker run --rm --env-file "$REPO/backend/.env" projeto-integrador-backend \
      python -c "import json; from src.main import create_app; print(json.dumps(create_app().openapi()))" > "$OUT/openapi.json" 2>/dev/null
  fi
  # 2) ZAP full (ativo, sem autenticação) e API scan (ativo, a partir do OpenAPI)
  rodar zap-full ghcr.io/zaproxy/zaproxy:stable -v "$OUT:/zap/wrk:rw" ghcr.io/zaproxy/zaproxy:stable \
    zap-full-scan.py -t "$TARGET_URL" -r zap-full.html -J zap-full.json
  if [ -s "$OUT/openapi.json" ]; then
    # A autenticação do ZAP via -z/replacer e a exclusão de /auth/logout e /auth/senha
    # (que encerrariam a própria sessão do scanner) devem ser validadas na 1ª execução.
    rodar zap-api ghcr.io/zaproxy/zaproxy:stable -v "$OUT:/zap/wrk:rw" ghcr.io/zaproxy/zaproxy:stable \
      zap-api-scan.py -t /zap/wrk/openapi.json -f openapi -r zap-api.html -J zap-api.json
  else
    registrar zap-api "NAO_EXECUTADO (sem openapi.json: faltou a imagem do backend ou backend/.env)"
  fi
  rodar nuclei-ativo projectdiscovery/nuclei:latest projectdiscovery/nuclei:latest \
    -u "$TARGET_URL" -tags exposure,misconfig,tech,default-login,sqli,xss,lfi,cve -severity low,medium,high,critical -silent -nc
  # 3) sqlmap no login (nível 2, risco 1); o marcador * indica o ponto de injeção
  rodar sqlmap python:3.12-slim python:3.12-slim \
    sh -c "pip install -q sqlmap && sqlmap -u '$TARGET_URL${API_PREFIX:-/api}/auth/login' \
      --data='{\"email\":\"a@exemplo.invalid*\",\"senha\":\"x\"}' \
      --headers='Content-Type: application/json\nOrigin: $TARGET_URL' --batch --level=2 --risk=1 --random-agent --flush-session"
}

case "$MODO" in
  codigo) codigo ;;
  rede) rede ;;
  passivo) passivo ;;
  pentest) pentest ;;
  ativo) ativo ;;
  tudo) codigo; rede; passivo; pentest ;;
  *) echo "Modo inválido. Use: codigo | rede | passivo | pentest | ativo | tudo"; exit 64 ;;
esac

[ "${SILENCIOSO:-0}" = "1" ] && exit 0   # executor cego: nada sobre resultados na saída

echo
echo "Relatório em: $OUT"
if grep -q "REPROVADO" "$RESUMO"; then echo "VEREDITO: REPROVADO"; exit 1; fi
if grep -q "NAO_EXECUTADO" "$RESUMO"; then echo "VEREDITO: INCOMPLETO (etapas não executadas não contam como aprovadas)"; exit 3; fi
echo "VEREDITO: APROVADO"
