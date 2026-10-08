"""Testes unitários da orquestração de troca de refil sem banco ou HTTP."""

from datetime import date, datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.repositories.exceptions import DataTrocaInvalida, ErroDeDominio
from src.services import troca_refil

_AGORA = datetime(2026, 3, 21, 12, tzinfo=timezone.utc)


def test_falhas_do_servico_sao_excecoes_de_dominio() -> None:
    """Permite capturar as validações do serviço por uma base comum."""
    assert issubclass(troca_refil.ArmadilhaNaoEncontrada, ErroDeDominio)
    assert issubclass(troca_refil.DataInstalacaoFutura, ErroDeDominio)


def _instalar_repositorios_falsos(
    monkeypatch: pytest.MonkeyPatch,
    *,
    armadilha: object | None,
    ativo: object | None,
    chamadas: list[str],
    erro_ao_encerrar: Exception | None = None,
) -> None:
    """Substitui repositórios por fakes que registram a ordem da operação."""

    class RepositorioArmadilha:
        def __init__(self, _session: object) -> None:
            pass

        def get_by_id_for_update(self, _armadilha_id):
            chamadas.append("bloquear_armadilha")
            return armadilha

    class RepositorioRefil:
        def __init__(self, _session: object) -> None:
            pass

        def get_active_for_armadilha(self, _armadilha_id):
            chamadas.append("buscar_ativo")
            return ativo

        def close(self, _refil_id, _data_troca):
            chamadas.append("encerrar")
            if erro_ao_encerrar is not None:
                raise erro_ao_encerrar
            return ativo

        def create(self, *, armadilha_id, data_instalacao):
            chamadas.append("criar")
            return SimpleNamespace(
                id=uuid4(),
                armadilha_id=armadilha_id,
                data_instalacao=data_instalacao,
            )

    monkeypatch.setattr(troca_refil, "ArmadilhaRepository", RepositorioArmadilha)
    monkeypatch.setattr(troca_refil, "RefilRepository", RepositorioRefil)


def test_trocar_refil_bloqueia_encerra_cria_e_monta_os_dias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    armadilha_id = uuid4()
    refil_anterior = SimpleNamespace(
        id=uuid4(),
        data_instalacao=date(2026, 3, 10),
    )
    chamadas: list[str] = []
    _instalar_repositorios_falsos(
        monkeypatch,
        armadilha=object(),
        ativo=refil_anterior,
        chamadas=chamadas,
    )

    resultado = troca_refil.trocar_refil(
        object(),
        armadilha_id,
        date(2026, 3, 21),
        _AGORA,
    )

    assert chamadas == ["bloquear_armadilha", "buscar_ativo", "encerrar", "criar"]
    assert resultado.refil_encerrado is not None
    assert resultado.refil_encerrado.id == refil_anterior.id
    assert resultado.refil_encerrado.dias_ate_troca == 11
    assert resultado.refil_novo.data_instalacao == date(2026, 3, 21)
    assert resultado.refil_novo.dias_em_uso == 0


def test_trocar_refil_sem_ciclo_ativo_cria_apenas_o_novo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chamadas: list[str] = []
    _instalar_repositorios_falsos(
        monkeypatch,
        armadilha=object(),
        ativo=None,
        chamadas=chamadas,
    )

    resultado = troca_refil.trocar_refil(
        object(),
        uuid4(),
        date(2026, 3, 21),
        _AGORA,
    )

    assert chamadas == ["bloquear_armadilha", "buscar_ativo", "criar"]
    assert resultado.refil_encerrado is None


def test_trocar_refil_rejeita_armadilha_ausente_antes_de_buscar_refil(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chamadas: list[str] = []
    _instalar_repositorios_falsos(
        monkeypatch,
        armadilha=None,
        ativo=None,
        chamadas=chamadas,
    )

    with pytest.raises(troca_refil.ArmadilhaNaoEncontrada):
        troca_refil.trocar_refil(
            object(),
            uuid4(),
            date(2026, 3, 21),
            _AGORA,
        )

    assert chamadas == ["bloquear_armadilha"]


def test_trocar_refil_rejeita_data_futura_antes_de_buscar_ciclo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chamadas: list[str] = []
    _instalar_repositorios_falsos(
        monkeypatch,
        armadilha=object(),
        ativo=None,
        chamadas=chamadas,
    )

    with pytest.raises(troca_refil.DataInstalacaoFutura):
        troca_refil.trocar_refil(
            object(),
            uuid4(),
            date(2026, 3, 22),
            _AGORA,
        )

    assert chamadas == ["bloquear_armadilha"]


def test_trocar_refil_propaga_data_anterior_rejeitada_pelo_repositorio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chamadas: list[str] = []
    _instalar_repositorios_falsos(
        monkeypatch,
        armadilha=object(),
        ativo=SimpleNamespace(id=uuid4(), data_instalacao=date(2026, 3, 20)),
        chamadas=chamadas,
        erro_ao_encerrar=DataTrocaInvalida(),
    )

    with pytest.raises(DataTrocaInvalida):
        troca_refil.trocar_refil(
            object(),
            uuid4(),
            date(2026, 3, 19),
            _AGORA,
        )

    assert chamadas == ["bloquear_armadilha", "buscar_ativo", "encerrar"]
