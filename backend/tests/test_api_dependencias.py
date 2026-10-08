"""Testes das dependências HTTP sem serviços externos."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy.orm import Session

from src.api.dependencias import get_agora, get_session


def test_get_session_fecha_sessao_sem_fazer_commit() -> None:
    sessao = Mock(spec=Session)
    fabrica = Mock(return_value=sessao)
    requisicao = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(session_factory=fabrica))
    )

    dependencia = get_session(requisicao)

    assert next(dependencia) is sessao
    with pytest.raises(StopIteration):
        next(dependencia)

    sessao.close.assert_called_once_with()
    sessao.commit.assert_not_called()


def test_get_agora_retorna_datetime_utc_com_fuso() -> None:
    agora = get_agora()

    assert agora.tzinfo is not None
    assert agora.utcoffset().total_seconds() == 0
