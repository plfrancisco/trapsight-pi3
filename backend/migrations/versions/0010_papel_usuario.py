"""Adiciona papéis e impede a existência de dois gerentes."""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Preserva contas existentes como operadores e restringe os papéis."""
    op.add_column(
        "usuario",
        sa.Column("papel", sa.String(8), nullable=False, server_default="operador"),
    )
    op.create_check_constraint(
        "ck_usuario_papel", "usuario", "papel IN ('gerente', 'operador')"
    )
    op.create_index(
        "uq_usuario_gerente",
        "usuario",
        ["papel"],
        unique=True,
        postgresql_where=sa.text("papel = 'gerente'"),
    )


def downgrade() -> None:
    """Remove restrições antes de remover a coluna de papel."""
    op.drop_index("uq_usuario_gerente", table_name="usuario")
    op.drop_constraint("ck_usuario_papel", "usuario", type_="check")
    op.drop_column("usuario", "papel")
