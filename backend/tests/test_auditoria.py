"""Integração da saída de auditoria com a criação da aplicação."""

from uuid import uuid4

import pytest


def test_auditoria_escreve_evento_em_stdout_sem_dados_proibidos(
    monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    """A configuração da aplicação publica um evento sem expor segredos."""
    for nome, valor in {
        "DATABASE_URL": "postgresql://db-ficticio:5432/armadilhas",
        "MODEL_WEIGHTS_PATH": "/tmp/pesos.pt",
        "MODEL_VERSION": "v0.1.0-test",
        "INFERENCE_MODE": "stub",
        "UPLOADS_DIR": "/tmp/uploads",
        "CORS_ORIGENS": "http://localhost:5173",
    }.items():
        monkeypatch.setenv(nome, valor)
    from src.main import create_app
    from src.services.auditoria import registrar_evento

    create_app()
    registrar_evento("login_ok", usuario_id=uuid4(), sessao_id=uuid4())

    saida, erro = capfd.readouterr()
    assert saida.count("auth.login_ok") == 1
    assert "usuario_id=" in saida
    assert "sessao_id=" in saida
    assert erro == ""
    for proibido in ("senha", "hash", "token", "email-digitado@exemplo.com"):
        assert proibido not in saida
