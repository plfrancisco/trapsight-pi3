"""Restringe as tabelas ao backend autenticado e habilita RLS no Supabase."""

import logging

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

_PAPEL = "trapsight_backend"
_TABELAS = (
    "armadilha",
    "refil",
    "analise",
    "modelo_armadilha",
    "usuario",
    "sessao",
    "tentativa_login",
)
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
    # O Compose de produção usa papéis próprios, sem CREATEROLE e sem PostgREST:
    # nele não há papel a restringir, então esta migração não faz nada.
    if not _papel_existe(_PAPEL):
        if not _pode_criar_papeis():
            _registro.info(
                "Sem permissão para criar %s; RLS por papel ignorado.", _PAPEL
            )
            return
        op.execute(f"CREATE ROLE {_PAPEL} NOLOGIN")

    op.execute(f"GRANT USAGE ON SCHEMA public TO {_PAPEL}")
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {_PAPEL}"
    )
    for tabela in _TABELAS:
        op.execute(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {tabela} TO {_PAPEL}"
        )
        op.execute(f"ALTER TABLE {tabela} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY trapsight_backend_access ON {tabela} "
            f"TO {_PAPEL} USING (true) WITH CHECK (true)"
        )


def downgrade() -> None:
    if not _papel_existe(_PAPEL):
        return
    for tabela in reversed(_TABELAS):
        op.execute(f"DROP POLICY IF EXISTS trapsight_backend_access ON {tabela}")
        op.execute(f"ALTER TABLE {tabela} DISABLE ROW LEVEL SECURITY")
        op.execute(f"REVOKE ALL ON TABLE {tabela} FROM {_PAPEL}")
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM {_PAPEL}"
    )
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {_PAPEL}")
    # O papel não é removido: papéis valem para o cluster inteiro e podem ser
    # usados por outros bancos; só as permissões deste banco são retiradas.
