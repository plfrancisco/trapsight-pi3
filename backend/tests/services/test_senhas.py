"""Testes da política, do hash e da verificação de senhas."""

import pytest

from src.services.senhas import (
    SenhaFraca,
    ServicoDeSenhas,
    normalizar_senha,
    validar_politica,
)

_EMAIL = "operador@exemplo.com"


def test_frase_longa_com_numero_e_aceita() -> None:
    validar_politica("uma frase longa e bem diferente 2026", email=_EMAIL)


@pytest.mark.parametrize("senha", ["cavalo9az", "9azulvela", "Boa8noite", "ação2026ok"])
def test_oito_caracteres_com_letra_e_numero_sao_aceitos(senha: str) -> None:
    validar_politica(senha, email=_EMAIL, nome="Maria Souza")


def test_exatamente_128_caracteres_sao_aceitos() -> None:
    senha = ("abcdefghij0123456789" * 7)[:128]
    assert len(senha) == 128
    validar_politica(senha, email=_EMAIL)


@pytest.mark.parametrize(
    ("senha", "motivo"),
    [
        ("cavalo9", "curta"),
        ("a1" * 65, "longa"),
        ("cavaloazul", "composicao"),
        ("12345678", "composicao"),
        ("!!!!????", "composicao"),
        ("PASSWORD1234567", "comum"),
        ("senhasenha123", "comum"),
        ("kq1kq1kq1kq1", "trivial"),
        ("ab1ab1ab1ab1", "trivial"),
        ("minha-trapsight-2026-ok", "contextual"),
        ("operador-de-2026-zzz", "contextual"),
    ],
)
def test_politica_recusa_senhas_fracas(senha: str, motivo: str) -> None:
    with pytest.raises(SenhaFraca) as erro:
        validar_politica(senha, email=_EMAIL, nome="Maria Souza")

    assert erro.value.motivo == motivo


def test_politica_recusa_parte_do_nome() -> None:
    with pytest.raises(SenhaFraca) as erro:
        validar_politica("souza-azul-cavalo-33", email=_EMAIL, nome="Maria Souza")

    assert erro.value.motivo == "contextual"


def test_normalizacao_nfc_equipara_formas_do_mesmo_texto() -> None:
    assert normalizar_senha("é") == normalizar_senha("é")


@pytest.fixture(scope="module")
def servico() -> ServicoDeSenhas:
    return ServicoDeSenhas(memoria_kib=19456, iteracoes=2, paralelismo=1)


def test_hash_e_argon2id_com_sal_unico(servico: ServicoDeSenhas) -> None:
    primeiro = servico.gerar_hash("uma frase longa e bem diferente 2026")
    segundo = servico.gerar_hash("uma frase longa e bem diferente 2026")

    assert primeiro.startswith("$argon2id$")
    assert "m=19456,t=2,p=1" in primeiro
    assert primeiro != segundo


def test_verificacao_aceita_a_certa_e_recusa_a_errada(servico: ServicoDeSenhas) -> None:
    armazenado = servico.gerar_hash("uma frase longa e bem diferente 2026")

    assert servico.verificar("uma frase longa e bem diferente 2026", armazenado) == (
        True,
        None,
    )
    assert servico.verificar("outra coisa qualquer", armazenado)[0] is False


def test_hash_desconhecido_nunca_autentica(servico: ServicoDeSenhas) -> None:
    assert servico.verificar("qualquer", "nao-e-um-hash") == (False, None)
    assert servico.verificar("qualquer", "") == (False, None)


def test_hash_com_parametros_antigos_pede_regravacao() -> None:
    antigo = ServicoDeSenhas(memoria_kib=8, iteracoes=1, paralelismo=1)
    atual = ServicoDeSenhas(memoria_kib=19456, iteracoes=2, paralelismo=1)
    armazenado = antigo.gerar_hash("uma frase longa e bem diferente 2026")

    confere, novo = atual.verificar("uma frase longa e bem diferente 2026", armazenado)

    assert confere is True
    assert novo is not None and "m=19456,t=2,p=1" in novo


def test_verificacao_fantasma_nao_lanca(servico: ServicoDeSenhas) -> None:
    servico.verificar_contra_ficticio("qualquer coisa")
