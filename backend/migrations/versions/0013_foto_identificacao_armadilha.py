"""Guarda a foto de identificação opcional da armadilha."""

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Acrescenta as colunas sem mexer em RLS nem em privilégios da tabela.

    Os privilégios e a política de linha de ``armadilha`` valem para a tabela
    inteira, então as colunas novas herdam o acesso dos papéis existentes.
    """
    op.add_column(
        "armadilha",
        sa.Column("foto_identificacao", sa.LargeBinary(), nullable=True),
    )
    op.add_column(
        "armadilha",
        sa.Column("foto_atualizada_em", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("armadilha", "foto_atualizada_em")
    op.drop_column("armadilha", "foto_identificacao")
