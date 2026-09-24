"""Define as tabelas relacionais do ciclo de vida e análise das armadilhas."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Cria armadilha, refil e análise com restrições para manter dados consistentes."""
    op.create_table(
        "armadilha",
        sa.Column(
            "id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("identificador", sa.String(), nullable=False),
        sa.Column("modelo", sa.String(), nullable=True),
        sa.Column("localizacao", sa.String(), nullable=True),
        sa.Column("data_instalacao", sa.Date(), nullable=True),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_armadilha"),
        sa.UniqueConstraint("identificador", name="uq_armadilha_identificador"),
    )
    op.create_table(
        "refil",
        sa.Column(
            "id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("armadilha_id", sa.UUID(), nullable=False),
        sa.Column("data_instalacao", sa.Date(), nullable=False),
        sa.Column("data_troca", sa.Date(), nullable=True),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_refil"),
        sa.ForeignKeyConstraint(
            ["armadilha_id"],
            ["armadilha.id"],
            name="fk_refil_armadilha_id",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "data_troca IS NULL OR data_troca >= data_instalacao", name="ck_refil_datas"
        ),
    )
    op.create_index("ix_refil_armadilha_id", "refil", ["armadilha_id"])
    op.create_table(
        "analise",
        sa.Column(
            "id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("refil_id", sa.UUID(), nullable=False),
        sa.Column("analisado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("percentual_coberto", sa.Numeric(5, 2), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("caminho_imagem", sa.String(), nullable=False),
        sa.Column("modelo_versao", sa.String(), nullable=False),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_analise"),
        sa.ForeignKeyConstraint(
            ["refil_id"], ["refil.id"], name="fk_analise_refil_id", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "percentual_coberto BETWEEN 0 AND 100", name="ck_analise_percentual_coberto"
        ),
        sa.CheckConstraint(
            "status IN ('ok', 'atencao', 'trocar')", name="ck_analise_status"
        ),
    )
    op.create_index(
        "ix_analise_refil_id_analisado_em", "analise", ["refil_id", "analisado_em"]
    )


def downgrade() -> None:
    """Remove as três tabelas em ordem inversa para respeitar as chaves estrangeiras."""
    op.drop_index("ix_analise_refil_id_analisado_em", table_name="analise")
    op.drop_table("analise")
    op.drop_index("ix_refil_armadilha_id", table_name="refil")
    op.drop_table("refil")
    op.drop_table("armadilha")
