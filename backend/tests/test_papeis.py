"""Restrições de papel verificadas diretamente no PostgreSQL migrado."""

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from src.entities import Usuario
from src.entities.papel import PapelUsuario


def test_migration_cria_default_check_e_indice_parcial(engine):
    inspetor = inspect(engine)
    coluna = next(c for c in inspetor.get_columns("usuario") if c["name"] == "papel")
    assert not coluna["nullable"]
    assert "operador" in coluna["default"]
    flag = next(
        c
        for c in inspetor.get_columns("usuario")
        if c["name"] == "troca_senha_pendente"
    )
    assert not flag["nullable"]
    assert "false" in flag["default"]
    assert any(
        c["name"] == "ck_usuario_papel"
        for c in inspetor.get_check_constraints("usuario")
    )
    indice = next(
        i for i in inspetor.get_indexes("usuario") if i["name"] == "uq_usuario_gerente"
    )
    assert indice["unique"]
    assert "gerente" in str(indice["dialect_options"]["postgresql_where"])


def test_banco_recusa_segundo_gerente_mesmo_se_primeiro_inativo(session):
    session.add(
        Usuario(
            email="gerente@exemplo.com",
            nome="Gerente",
            senha_hash="hash",
            papel=PapelUsuario.GERENTE,
            ativo=False,
        )
    )
    session.flush()
    with pytest.raises(IntegrityError):
        with session.begin_nested():
            session.add(
                Usuario(
                    email="segundo@exemplo.com",
                    nome="Segundo",
                    senha_hash="hash",
                    papel=PapelUsuario.GERENTE,
                )
            )
            session.flush()


def test_banco_recusa_papel_desconhecido(session):
    usuario = Usuario(email="operador@exemplo.com", nome="Operador", senha_hash="hash")
    session.add(usuario)
    session.flush()
    assert usuario.papel == PapelUsuario.OPERADOR
    with pytest.raises(IntegrityError):
        with session.begin_nested():
            session.execute(
                text("UPDATE usuario SET papel = :papel WHERE id = :id"),
                {"papel": "admin", "id": usuario.id},
            )
