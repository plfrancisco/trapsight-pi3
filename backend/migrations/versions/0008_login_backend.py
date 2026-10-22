"""Cria a conta sem privilégio de login usada pelo serviço FastAPI."""

import logging

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

_PAPEL_BACKEND = "trapsight_backend"
_PAPEL_RUNTIME = "trapsight_runtime"
_registro = logging.getLogger("alembic.runtime.migration")


def _papel_existe(nome: str) -> bool:
    return bool(
        op.get_bind()
        .execute(
            sa.text("SELECT 1 FROM pg_roles WHERE rolname = :nome"), {"nome": nome}
        )
        .scalar()
    )


def _pode_criar_papeis() -> bool:
    return bool(
        op.get_bind()
        .execute(
            sa.text(
                "SELECT rolcreaterole OR rolsuper FROM pg_roles "
                "WHERE rolname = current_user"
            )
        )
        .scalar()
    )


def upgrade() -> None:
    # Sem o papel da 0007 (Compose de produção), não há nada a conceder.
    if not _papel_existe(_PAPEL_BACKEND):
        _registro.info("%s ausente; conta de login não criada.", _PAPEL_BACKEND)
        return
    if not _papel_existe(_PAPEL_RUNTIME):
        if not _pode_criar_papeis():
            _registro.info("Sem permissão para criar %s; ignorado.", _PAPEL_RUNTIME)
            return
        # Sem senha: ela é definida fora do repositório, pelo administrador do banco.
        op.execute(
            f"CREATE ROLE {_PAPEL_RUNTIME} LOGIN INHERIT "
            "NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS"
        )
    op.execute(f"GRANT {_PAPEL_BACKEND} TO {_PAPEL_RUNTIME}")


def downgrade() -> None:
    if not _papel_existe(_PAPEL_RUNTIME):
        return
    # A conta de login não é removida: papéis valem para o cluster inteiro e
    # podem ser usados por outros bancos; só a herança do papel é retirada.
    op.execute(f"REVOKE {_PAPEL_BACKEND} FROM {_PAPEL_RUNTIME}")
