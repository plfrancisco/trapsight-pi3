"""Guarda as imagens da análise no banco quando o armazenamento é remoto."""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "analise",
        sa.Column("imagem_original", sa.LargeBinary(), nullable=True),
    )
    op.add_column(
        "analise",
        sa.Column("mascara", sa.LargeBinary(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("analise", "mascara")
    op.drop_column("analise", "imagem_original")
