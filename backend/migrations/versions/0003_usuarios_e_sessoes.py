"""Contas de usuário, sessões autenticadas e registro de tentativas de login."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def _id_e_criado_em() -> list[sa.Column]:
    """Colunas comuns: identificador e instante de criação gerados pelo banco."""
    return [
        sa.Column(
            "id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    """Cria usuario, sessao e tentativa_login com as restrições no banco."""
    id_, criado_em = _id_e_criado_em()
    op.create_table(
        "usuario",
        id_,
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("nome", sa.String(), nullable=False),
        sa.Column("senha_hash", sa.String(), nullable=False),
        sa.Column("ativo", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("bloqueado_ate", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "senha_alterada_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("ultimo_login_em", sa.DateTime(timezone=True), nullable=True),
        criado_em,
        sa.PrimaryKeyConstraint("id", name="pk_usuario"),
        sa.UniqueConstraint("email", name="uq_usuario_email"),
    )

    id_, criado_em = _id_e_criado_em()
    op.create_table(
        "sessao",
        id_,
        sa.Column("usuario_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("csrf_token", sa.String(), nullable=False),
        sa.Column(
            "ultimo_uso_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expira_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revogada_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip", sa.String(), nullable=True),
        sa.Column("user_agent", sa.String(), nullable=True),
        criado_em,
        sa.PrimaryKeyConstraint("id", name="pk_sessao"),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuario.id"],
            name="fk_sessao_usuario_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("token_hash", name="uq_sessao_token_hash"),
        sa.CheckConstraint(
            "token_hash ~ '^[0-9a-f]{64}$'", name="ck_sessao_token_hash_sha256"
        ),
    )
    op.create_index(
        "ix_sessao_usuario_id_revogada_em", "sessao", ["usuario_id", "revogada_em"]
    )

    id_, criado_em = _id_e_criado_em()
    op.create_table(
        "tentativa_login",
        id_,
        sa.Column("identificador_hash", sa.String(), nullable=False),
        sa.Column("ip", sa.String(), nullable=False),
        sa.Column(
            "ocorrida_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("sucesso", sa.Boolean(), nullable=False),
        criado_em,
        sa.PrimaryKeyConstraint("id", name="pk_tentativa_login"),
    )
    op.create_index(
        "ix_tentativa_login_identificador_hash_ocorrida_em",
        "tentativa_login",
        ["identificador_hash", "ocorrida_em"],
    )
    op.create_index(
        "ix_tentativa_login_ip_ocorrida_em", "tentativa_login", ["ip", "ocorrida_em"]
    )


def downgrade() -> None:
    """Remove as tabelas de autenticação na ordem inversa das dependências."""
    op.drop_index("ix_tentativa_login_ip_ocorrida_em", table_name="tentativa_login")
    op.drop_index(
        "ix_tentativa_login_identificador_hash_ocorrida_em",
        table_name="tentativa_login",
    )
    op.drop_table("tentativa_login")
    op.drop_index("ix_sessao_usuario_id_revogada_em", table_name="sessao")
    op.drop_table("sessao")
    op.drop_table("usuario")
