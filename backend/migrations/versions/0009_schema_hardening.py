"""Protege a versão das migrations e indexa o catálogo de modelos."""

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE public.alembic_version ENABLE ROW LEVEL SECURITY")
    op.create_index("ix_armadilha_modelo_id", "armadilha", ["modelo_id"])


def downgrade() -> None:
    op.drop_index("ix_armadilha_modelo_id", table_name="armadilha")
    op.execute("ALTER TABLE public.alembic_version DISABLE ROW LEVEL SECURITY")
