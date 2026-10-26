"""Identifica contas que devem substituir a senha inicial."""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Preserva o acesso das contas existentes sem impor troca retroativa."""
    op.add_column(
        "usuario",
        sa.Column(
            "troca_senha_pendente",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    """Remove a indicação de troca inicial obrigatória."""
    op.drop_column("usuario", "troca_senha_pendente")
