"""Catálogo de modelos de armadilha e vínculo opcional com cada armadilha."""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Cria modelo_armadilha, cadastra o StickFly K-45 e liga armadilha.modelo_id."""
    op.create_table(
        "modelo_armadilha",
        sa.Column(
            "id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("codigo", sa.String(), nullable=False),
        sa.Column("nome", sa.String(), nullable=False),
        sa.Column("fabricante", sa.String(), nullable=False),
        sa.Column("descricao", sa.String(), nullable=True),
        sa.Column("atracao", sa.String(), nullable=True),
        sa.Column("refil_largura_mm", sa.Integer(), nullable=False),
        sa.Column("refil_altura_mm", sa.Integer(), nullable=False),
        sa.Column("ativo", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_modelo_armadilha"),
        sa.UniqueConstraint("codigo", name="uq_modelo_armadilha_codigo"),
        sa.CheckConstraint(
            "refil_largura_mm > 0 AND refil_altura_mm > 0",
            name="ck_modelo_armadilha_refil_positivo",
        ),
    )
    op.execute(
        """
        INSERT INTO modelo_armadilha
            (codigo, nome, fabricante, descricao, atracao,
             refil_largura_mm, refil_altura_mm)
        VALUES
            ('stickfly-k45', 'StickFly K-45', 'StickFly',
             'Armadilha de parede com 3 lâmpadas UVA de 15 W e refil adesivo '
             'de 450 x 220 mm. Cobre 60 m2 e captura insetos voadores.',
             'UV-A', 450, 220)
        """
    )
    op.add_column("armadilha", sa.Column("modelo_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_armadilha_modelo_id",
        "armadilha",
        "modelo_armadilha",
        ["modelo_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.execute(
        """
        UPDATE armadilha SET modelo_id = m.id
        FROM modelo_armadilha m
        WHERE lower(armadilha.modelo) IN (lower(m.nome), lower(m.codigo))
        """
    )
    op.execute(
        """
        UPDATE armadilha SET modelo = m.nome
        FROM modelo_armadilha m WHERE armadilha.modelo_id = m.id
        """
    )


def downgrade() -> None:
    """Remove o vínculo e o catálogo; o nome do modelo segue em armadilha.modelo."""
    op.drop_constraint("fk_armadilha_modelo_id", "armadilha", type_="foreignkey")
    op.drop_column("armadilha", "modelo_id")
    op.drop_table("modelo_armadilha")
