#!/usr/bin/env bash
# Prova que o backup do banco é restaurável, em um PostgreSQL descartável.
#
# Um backup que nunca foi restaurado não é um backup: este script popula um
# banco próprio (migrações, contas, análises com imagem), chama
# scripts/backup-banco.sh, destrói o banco e chama scripts/restaurar-banco.sh.
# Depois compara contagem de linhas por tabela, o SHA-256 de cada imagem
# guardada em BYTEA e um login real do gerente. Também confirma que a
# restauração se recusa a rodar sobre um banco que já tem tabelas.
#
# Nada aqui toca o banco de desenvolvimento nem o de produção: o contêiner, a
# rede, o par de chaves e o diretório do backup são criados e removidos pelo
# próprio script.
#
# Variáveis de ambiente:
#   TESTE_CIFRA   cms (padrão, convenção do repositório) ou gpg
#   TESTE_PAR     descartavel (padrão) gera um par de chaves só para o teste;
#                 projeto usa o par real do backup, para conferir os caminhos
#                 que valem em produção. O padrão não exige a chave privada do
#                 projeto, de modo que o teste rode em qualquer máquina.
#
# Uso (na raiz do repositório, com o Docker ativo):
#   scripts/testar-restauracao.sh
set -euo pipefail
export MSYS_NO_PATHCONV=1

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"

# O openssl nativo do Windows não entende caminhos /c/...; o cygpath os converte.
winpath() { cygpath -m "$1" 2>/dev/null || echo "$1"; }

CIFRA="${TESTE_CIFRA:-cms}"
case "$CIFRA" in
  cms | gpg) ;;
  *) echo "TESTE_CIFRA aceita apenas cms ou gpg." >&2; exit 64 ;;
esac

PAR="${TESTE_PAR:-descartavel}"
case "$PAR" in
  descartavel) ;;
  projeto)
    if [ "$CIFRA" != cms ]; then
      echo "TESTE_PAR=projeto só vale com TESTE_CIFRA=cms." >&2
      exit 64
    fi
    ;;
  *) echo "TESTE_PAR aceita apenas descartavel ou projeto." >&2; exit 64 ;;
esac

# Nomes próprios, distintos dos de qualquer outra pilha do projeto, para que o
# teste nunca alcance o banco de desenvolvimento.
REDE="pi-backup-restauracao"
BANCO="pi-backup-restauracao-db"
IMAGEM_PG="postgres:17.6-alpine"
BANCO_NOME="armadilhas"

EMAIL_GERENTE="gerente.restauracao@exemplo.invalid"
EMAIL_OPERADOR="operador.restauracao@exemplo.invalid"
# Senhas longas e aleatórias: a política recusa senhas curtas, comuns ou
# derivadas do e-mail, do nome ou do produto.
gerar_senha() { printf 'Rx-%s' "$(openssl rand -hex 12)"; }
SENHA_ADMIN="$(openssl rand -hex 16)"
SENHA_GERENTE="$(gerar_senha)"
SENHA_OPERADOR="$(gerar_senha)"

TMP="$(mktemp -d)"
chmod 700 "$TMP"
COFRE="$TMP/cofre"
# Sobrescrita pelo ramo de cifra escolhido; o ramo gpg não a usa.
CHAVE_TESTE="$TMP/chave.pem"

limpar() {
  docker rm -f "$BANCO" >/dev/null 2>&1 || true
  docker network rm "$REDE" >/dev/null 2>&1 || true
  rm -rf "$TMP"
}
trap limpar EXIT

URL_BANCO="postgresql://root:$SENHA_ADMIN@$BANCO:5432/$BANCO_NOME"

sql() {
  docker exec -i "$BANCO" psql -U root -d "${2:-$BANCO_NOME}" -tAq -v ON_ERROR_STOP=1 -c "$1"
}

rodar_backend() {
  docker run --rm -i --network "$REDE" \
    -v "$RAIZ/backend:/b" -v uvcache:/root/.cache/uv -w /b \
    -e UV_PROJECT_ENVIRONMENT=/tmp/venv -e PYTHONPATH=/b \
    -e DATABASE_URL="$URL_BANCO" \
    -e MODEL_WEIGHTS_PATH=/tmp/pesos.pt -e MODEL_VERSION=v0.1.0-dev \
    -e INFERENCE_MODE=stub -e UPLOADS_DIR=/tmp/uploads \
    -e CORS_ORIGENS=http://localhost:5173 \
    -e EMAIL_GERENTE="$EMAIL_GERENTE" -e EMAIL_OPERADOR="$EMAIL_OPERADOR" \
    -e SENHA_GERENTE="$SENHA_GERENTE" -e SENHA_OPERADOR="$SENHA_OPERADOR" \
    ghcr.io/astral-sh/uv:python3.12-bookworm-slim \
    sh -c "$1"
}

TABELAS="alembic_version analise armadilha modelo_armadilha refil sessao tentativa_login usuario"
consulta_contagens() {
  local consulta=""
  for tabela in $TABELAS; do
    consulta="${consulta}SELECT '$tabela' AS t, count(*) FROM $tabela UNION ALL "
  done
  printf '%s ORDER BY t' "${consulta% UNION ALL }"
}
# O hash do BYTEA é calculado dentro do banco: compara o conteúdo realmente
# persistido, sem depender de como o cliente leria a coluna.
CONSULTA_IMAGENS="SELECT caminho_imagem
    || '|' || octet_length(imagem_original)
    || '|' || encode(sha256(imagem_original), 'hex')
    || '|' || octet_length(mascara)
    || '|' || encode(sha256(mascara), 'hex')
  FROM analise ORDER BY caminho_imagem"

echo "==> 1/9 PostgreSQL descartável ($IMAGEM_PG)"
limpar
docker network create "$REDE" >/dev/null
docker run -d --name "$BANCO" --network "$REDE" \
  -e POSTGRES_USER=root -e POSTGRES_PASSWORD="$SENHA_ADMIN" -e POSTGRES_DB="$BANCO_NOME" \
  "$IMAGEM_PG" >/dev/null
# A imagem oficial sobe um servidor temporário para a inicialização e depois
# reinicia; só o segundo "ready" indica o servidor definitivo.
for _ in $(seq 1 60); do
  [ "$(docker logs "$BANCO" 2>&1 | grep -c 'ready to accept connections')" -ge 2 ] && break
  sleep 1
done

echo "==> 2/9 migrações"
rodar_backend "uv sync --quiet --locked >/dev/null 2>&1 && uv run --quiet alembic upgrade head"

echo "==> 3/9 dados: gerente, operador e análises com imagem"
rodar_backend "uv run --quiet python -" <<'PY'
"""Popula o banco do teste de restauração com dados verificáveis."""

import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from src.cli import criar_usuario
from src.config.database import create_database_engine, create_session_factory
from src.config.settings import Settings
from src.entities import Analise, Armadilha, Refil
from src.entities.papel import PapelUsuario
from src.entities.status import StatusAnalise
from src.services.senhas import ServicoDeSenhas

# Percentual, status e tamanho das mídias de cada análise criada.
CENARIOS = (
    (Decimal("3.50"), StatusAnalise.OK, 4096, 2048),
    (Decimal("12.25"), StatusAnalise.ATENCAO, 8192, 3072),
    (Decimal("44.00"), StatusAnalise.TROCAR, 16384, 5120),
)


def midia(semente: int, tamanho: int) -> bytes:
    """Gera bytes reproduzíveis, incluindo 0x00, para exercitar o BYTEA."""
    return bytes((semente * 31 + indice) % 256 for indice in range(tamanho))


settings = Settings()
senhas = ServicoDeSenhas(
    memoria_kib=settings.argon2_memoria_kib,
    iteracoes=settings.argon2_iteracoes,
    paralelismo=settings.argon2_paralelismo,
)
engine = create_database_engine(settings.database_url.get_secret_value())
agora = datetime.now(timezone.utc)
try:
    with create_session_factory(engine)() as session:
        criar_usuario(
            session,
            senhas,
            email=os.environ["EMAIL_GERENTE"],
            nome="Gerente da Operacao",
            senha=os.environ["SENHA_GERENTE"],
            papel=PapelUsuario.GERENTE,
        )
        criar_usuario(
            session,
            senhas,
            email=os.environ["EMAIL_OPERADOR"],
            nome="Operador de Campo",
            senha=os.environ["SENHA_OPERADOR"],
            papel=PapelUsuario.OPERADOR,
        )
        armadilha = Armadilha(
            identificador="ARM-RST-001",
            localizacao="Galpao do teste de restauracao",
            data_instalacao=date(2026, 10, 1),
        )
        session.add(armadilha)
        session.flush()
        refil = Refil(armadilha_id=armadilha.id, data_instalacao=date(2026, 10, 1))
        session.add(refil)
        session.flush()
        for indice, (percentual, status, bytes_original, bytes_mascara) in enumerate(
            CENARIOS, start=1
        ):
            session.add(
                Analise(
                    refil_id=refil.id,
                    analisado_em=agora - timedelta(days=len(CENARIOS) - indice),
                    percentual_coberto=percentual,
                    status=status.value,
                    caminho_imagem=f"analise-{indice}/original.png",
                    imagem_original=midia(indice, bytes_original),
                    mascara=midia(indice + 100, bytes_mascara),
                    modelo_versao="v0.1.0-dev",
                )
            )
        session.commit()
finally:
    engine.dispose()
print("dados criados")
PY

echo "==> 4/9 estado antes do backup"
ANTES_CONTAGENS="$(sql "$(consulta_contagens)")"
ANTES_IMAGENS="$(sql "$CONSULTA_IMAGENS")"
printf '%s\n' "$ANTES_CONTAGENS" | sed 's/^/    /'

echo "==> 5/9 par de chaves ($PAR) e backup cifrado ($CIFRA)"
mkdir -p "$COFRE"
if [ "$CIFRA" = gpg ]; then
  export GNUPGHOME="$TMP/gnupg"
  mkdir -p "$GNUPGHOME"
  chmod 700 "$GNUPGHOME"
  DESTINATARIO="restauracao.teste@exemplo.invalid"
  gpg --batch --quiet --pinentry-mode loopback --passphrase "" \
    --quick-generate-key "$DESTINATARIO" default default never
  SAIDA_BACKUP="$(
    BACKUP_DATABASE_URL="$URL_BANCO" BACKUP_DIR="$COFRE" \
    BACKUP_DOCKER_REDE="$REDE" BACKUP_GPG_DESTINATARIO="$DESTINATARIO" \
      bash "$RAIZ/scripts/backup-banco.sh"
  )"
elif [ "$PAR" = projeto ]; then
  CERTIFICADO_TESTE="$RAIZ/security/cifra/backup-certificado.pem"
  CHAVE_TESTE="$HOME/.trapsight-backup/chave_privada.pem"
  for arquivo in "$CERTIFICADO_TESTE" "$CHAVE_TESTE"; do
    [ -f "$arquivo" ] || {
      echo "TESTE_PAR=projeto exige o par real; ausente: $arquivo" >&2
      exit 66
    }
  done
  SAIDA_BACKUP="$(
    BACKUP_DATABASE_URL="$URL_BANCO" BACKUP_DIR="$COFRE" \
    BACKUP_DOCKER_REDE="$REDE" BACKUP_CERTIFICADO="$CERTIFICADO_TESTE" \
      bash "$RAIZ/scripts/backup-banco.sh"
  )"
else
  # Par descartável no formato do repositório (openssl cms): a chave privada do
  # projeto não participa do teste.
  CERTIFICADO_TESTE="$TMP/certificado.pem"
  CHAVE_TESTE="$TMP/chave.pem"
  openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj "/CN=teste-restauracao" \
    -keyout "$(winpath "$CHAVE_TESTE")" \
    -out "$(winpath "$CERTIFICADO_TESTE")" 2>/dev/null
  chmod 600 "$CHAVE_TESTE"
  SAIDA_BACKUP="$(
    BACKUP_DATABASE_URL="$URL_BANCO" BACKUP_DIR="$COFRE" \
    BACKUP_DOCKER_REDE="$REDE" BACKUP_CERTIFICADO="$CERTIFICADO_TESTE" \
      bash "$RAIZ/scripts/backup-banco.sh"
  )"
fi
printf '%s\n' "$SAIDA_BACKUP" | sed 's/^/    /'
ARQUIVO="$(printf '%s\n' "$SAIDA_BACKUP" | sed -n 's/^Backup cifrado: //p')"
[ -f "$ARQUIVO" ] || { echo "O backup não foi gerado." >&2; exit 70; }

echo "==> 6/9 a restauração recusa banco com tabelas"
if RESTORE_DATABASE_URL="$URL_BANCO" RESTORE_DOCKER_REDE="$REDE" \
   RESTORE_CHAVE_PRIVADA="$CHAVE_TESTE" \
     bash "$RAIZ/scripts/restaurar-banco.sh" "$ARQUIVO" >/dev/null 2>&1; then
  echo "A restauração aceitou um banco já populado; o teste falha aqui." >&2
  exit 70
fi
echo "    recusou, como esperado"

echo "==> 7/9 destruindo o banco"
sql "SELECT pg_terminate_backend(pid) FROM pg_stat_activity
     WHERE datname = '$BANCO_NOME' AND pid <> pg_backend_pid()" postgres >/dev/null
docker exec "$BANCO" dropdb -U root --force "$BANCO_NOME"
docker exec "$BANCO" createdb -U root "$BANCO_NOME"
echo "    tabelas no banco recriado: $(sql "SELECT count(*) FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE c.relkind IN ('r', 'p') AND n.nspname = 'public'")"

echo "==> 8/9 restaurando"
RESTORE_DATABASE_URL="$URL_BANCO" RESTORE_DOCKER_REDE="$REDE" \
RESTORE_CHAVE_PRIVADA="$CHAVE_TESTE" \
  bash "$RAIZ/scripts/restaurar-banco.sh" "$ARQUIVO" | sed 's/^/    /'

echo "==> 9/9 conferindo"
DEPOIS_CONTAGENS="$(sql "$(consulta_contagens)")"
DEPOIS_IMAGENS="$(sql "$CONSULTA_IMAGENS")"
printf '%s\n' "$DEPOIS_CONTAGENS" | sed 's/^/    /'

falhou=0
if [ "$ANTES_CONTAGENS" != "$DEPOIS_CONTAGENS" ]; then
  echo "DIVERGÊNCIA nas contagens:" >&2
  diff <(printf '%s\n' "$ANTES_CONTAGENS") <(printf '%s\n' "$DEPOIS_CONTAGENS") >&2 || true
  falhou=1
fi
if [ "$ANTES_IMAGENS" != "$DEPOIS_IMAGENS" ]; then
  echo "DIVERGÊNCIA nas imagens (tamanho ou SHA-256):" >&2
  diff <(printf '%s\n' "$ANTES_IMAGENS") <(printf '%s\n' "$DEPOIS_IMAGENS") >&2 || true
  falhou=1
fi

LOGIN="$(rodar_backend "uv run --quiet python -" <<'PY'
"""Confirma que a senha do gerente continua válida depois da restauração."""

import os
from datetime import datetime, timezone

from src.config.database import create_database_engine, create_session_factory
from src.config.settings import Settings
from src.services.autenticacao import ServicoDeAutenticacao
from src.services.senhas import ServicoDeSenhas

settings = Settings()
senhas = ServicoDeSenhas(
    memoria_kib=settings.argon2_memoria_kib,
    iteracoes=settings.argon2_iteracoes,
    paralelismo=settings.argon2_paralelismo,
)
engine = create_database_engine(settings.database_url.get_secret_value())
try:
    with create_session_factory(engine)() as session:
        resultado = ServicoDeAutenticacao(session, settings, senhas).entrar(
            os.environ["EMAIL_GERENTE"],
            os.environ["SENHA_GERENTE"],
            ip="127.0.0.1",
            user_agent="teste-restauracao",
            agora=datetime.now(timezone.utc),
        )
        papel = resultado.usuario.papel.value
        session.commit()
finally:
    engine.dispose()
print(f"login valido papel={papel}")
PY
)"
printf '    %s\n' "$LOGIN"
case "$LOGIN" in
  *"login valido papel=gerente"*) ;;
  *) echo "O login do gerente não foi aceito após a restauração." >&2; falhou=1 ;;
esac

echo
if [ "$falhou" -ne 0 ]; then
  echo "TESTE DE RESTAURAÇÃO: FALHOU"
  exit 70
fi
LINHAS="$(printf '%s\n' "$DEPOIS_CONTAGENS" | awk -F'|' '{soma += $2} END {print soma}')"
echo "TESTE DE RESTAURAÇÃO: OK (cifra $CIFRA, par $PAR)"
echo "Tabelas conferidas: $(printf '%s\n' "$DEPOIS_CONTAGENS" | grep -c '')"
echo "Linhas conferidas: $LINHAS"
echo "Análises com imagem conferidas por SHA-256: $(printf '%s\n' "$DEPOIS_IMAGENS" | grep -c '')"
