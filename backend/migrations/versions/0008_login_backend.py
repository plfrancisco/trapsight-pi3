"""Cria a conta sem privilégio de login usada pelo serviço FastAPI."""

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_roles WHERE rolname = 'trapsight_runtime'
            ) THEN
                CREATE ROLE trapsight_runtime LOGIN INHERIT
                    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
            END IF;
        END
        $$;
        """
    )
    op.execute("GRANT trapsight_backend TO trapsight_runtime")


def downgrade() -> None:
    op.execute("REVOKE trapsight_backend FROM trapsight_runtime")
    op.execute("DROP ROLE trapsight_runtime")
