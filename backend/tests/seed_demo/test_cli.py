"""Confere a proteção de ambiente da execução explícita."""

import pytest

from src.seed_demo import ErroSeedDemo, validar_ambiente


def test_destino_de_producao_exige_confirmacao_sem_revelar_senha() -> None:
    """A recusa identifica o host sem reproduzir credenciais da URL."""
    url = "postgresql://usuario:senha-secreta@db.prod.example:5432/trapsight"

    with pytest.raises(ErroSeedDemo) as erro:
        validar_ambiente(url, "producao", False)

    mensagem = str(erro.value)
    assert "db.prod.example:5432/trapsight" in mensagem
    assert "senha-secreta" not in mensagem
    assert "--confirmar-ambiente" in mensagem


def test_confirmacao_permite_destino_de_producao() -> None:
    """A flag explícita libera o destino e retorna sua descrição segura."""
    destino = validar_ambiente(
        "postgresql://usuario:senha@db.prod.example:5432/trapsight",
        "producao",
        True,
    )

    assert destino == "db.prod.example:5432/trapsight"
