"""A série temporal exige no máximo um ciclo aberto por armadilha."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Impede ciclos ativos duplicados para preservar a série temporal."""
    op.create_index(
        "uq_refil_ativo_por_armadilha",
        "refil",
        ["armadilha_id"],
        unique=True,
        postgresql_where=sa.text("data_troca IS NULL"),
    )


def downgrade() -> None:
    """Remove o índice que limita os ciclos ativos por armadilha."""
    op.drop_index("uq_refil_ativo_por_armadilha", table_name="refil")
