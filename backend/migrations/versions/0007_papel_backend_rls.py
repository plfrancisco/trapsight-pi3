"""Restringe as tabelas ao backend autenticado e habilita RLS no Supabase."""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

_TABELAS = (
    "armadilha",
    "refil",
    "analise",
    "modelo_armadilha",
    "usuario",
    "sessao",
    "tentativa_login",
)


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_roles WHERE rolname = 'trapsight_backend'
            ) THEN
                CREATE ROLE trapsight_backend NOLOGIN;
            END IF;
        END
        $$;
        """
    )
    op.execute("GRANT USAGE ON SCHEMA public TO trapsight_backend")
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO trapsight_backend"
    )

    for tabela in _TABELAS:
        op.execute(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {tabela} "
            "TO trapsight_backend"
        )
        op.execute(f"ALTER TABLE {tabela} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY trapsight_backend_access ON {tabela} "
            "TO trapsight_backend USING (true) WITH CHECK (true)"
        )


def downgrade() -> None:
    for tabela in reversed(_TABELAS):
        op.execute(f"DROP POLICY trapsight_backend_access ON {tabela}")
        op.execute(f"ALTER TABLE {tabela} DISABLE ROW LEVEL SECURITY")
        op.execute(f"REVOKE ALL ON TABLE {tabela} FROM trapsight_backend")
    op.execute("REVOKE USAGE ON SCHEMA public FROM trapsight_backend")
    op.execute("DROP ROLE trapsight_backend")
