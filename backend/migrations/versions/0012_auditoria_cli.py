"""Persiste auditoria das ações administrativas executadas pela CLI."""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

_PAPEIS = ("trapsight_backend", "trapsight_app")


def _papeis_existentes() -> list[str]:
    """Retorna somente os papéis de execução já configurados no banco."""
    bind = op.get_bind()
    return [
        papel
        for papel in _PAPEIS
        if bind.execute(
            sa.text("SELECT 1 FROM pg_roles WHERE rolname = :papel"),
            {"papel": papel},
        ).scalar()
    ]


def upgrade() -> None:
    """Cria o histórico append-only e libera leitura e inserção ao backend."""
    op.create_table(
        "auditoria_cli",
        sa.Column(
            "id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column(
            "ocorrido_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("evento", sa.String(32), nullable=False),
        sa.Column("executor", sa.String(255), nullable=False),
        sa.Column("conta_alvo", sa.UUID(), nullable=True),
        sa.Column("resultado", sa.String(8), nullable=False),
        sa.Column("detalhe", sa.String(240), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_auditoria_cli"),
        sa.CheckConstraint(
            "evento IN ('criar-usuario', 'definir-papel', 'redefinir-senha', "
            "'ativar-usuario', 'desativar-usuario', 'desbloquear-usuario')",
            name="ck_auditoria_cli_evento",
        ),
        sa.CheckConstraint(
            "resultado IN ('sucesso', 'falha')", name="ck_auditoria_cli_resultado"
        ),
    )
    op.create_index("ix_auditoria_cli_ocorrido_em", "auditoria_cli", ["ocorrido_em"])
    op.execute("REVOKE ALL PRIVILEGES ON TABLE auditoria_cli FROM PUBLIC")
    op.execute("ALTER TABLE auditoria_cli ENABLE ROW LEVEL SECURITY")

    papeis = _papeis_existentes()
    if not papeis:
        return

    papeis_sql = ", ".join(papeis)
    for papel in papeis:
        op.execute(f"REVOKE UPDATE, DELETE ON TABLE auditoria_cli FROM {papel}")
        op.execute(f"GRANT SELECT, INSERT ON TABLE auditoria_cli TO {papel}")

    op.execute(
        "CREATE POLICY auditoria_cli_select ON auditoria_cli "
        f"FOR SELECT TO {papeis_sql} USING (true)"
    )
    op.execute(
        "CREATE POLICY auditoria_cli_insert ON auditoria_cli "
        f"FOR INSERT TO {papeis_sql} WITH CHECK (true)"
    )


def downgrade() -> None:
    """Remove a tabela e as políticas associadas."""
    op.drop_table("auditoria_cli")
