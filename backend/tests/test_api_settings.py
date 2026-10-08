"""Valida configurações e comportamento HTTP básico sem acessar serviços externos."""

import pytest
from fastapi.testclient import TestClient

from src.config.settings import Settings, SettingsConfigurationError

_FAKE_DATABASE_URL = "postgresql://db-ficticio:5432/armadilhas"
_REQUIRED_ENVIRONMENT = {
    "DATABASE_URL": _FAKE_DATABASE_URL,
    "MODEL_WEIGHTS_PATH": "/caminho-ficticio/pesos.pt",
    "MODEL_VERSION": "v0.1.0-dev",
    "UPLOADS_DIR": "/diretorio-ficticio/uploads",
    "CORS_ORIGENS": "http://localhost:5173",
}


@pytest.fixture
def fake_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fornece valores fictícios para criar configurações sem serviços reais."""
    for name, value in _REQUIRED_ENVIRONMENT.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("LIMIAR_ATENCAO", raising=False)
    monkeypatch.delenv("LIMIAR_TROCAR", raising=False)


def test_app_exposes_docs_and_keeps_settings_at_initialization(
    fake_environment: None,
) -> None:
    """Cria a aplicação sem conectar ao banco e disponibiliza sua configuração."""
    from src.main import app

    response = TestClient(app).get("/docs")

    assert response.status_code == 200
    assert app.state.settings.model_weights_path == "/caminho-ficticio/pesos.pt"
    assert app.state.settings.cors_origens == ["http://localhost:5173"]


def test_cors_accepts_list_with_spaces_and_rejects_other_origins(
    fake_environment: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Permite somente origens configuradas depois de remover espaços residuais."""
    from src.main import create_app

    monkeypatch.setenv(
        "CORS_ORIGENS",
        "http://localhost:5173, https://painel.ficticio.test",
    )
    client = TestClient(create_app())
    allowed = client.options(
        "/api/recurso",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    rejected = client.options(
        "/api/recurso",
        headers={
            "Origin": "https://origem-nao-listada.test",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert rejected.status_code == 400
    assert "access-control-allow-origin" not in rejected.headers


@pytest.mark.parametrize(
    "variable",
    [
        "DATABASE_URL",
        "MODEL_WEIGHTS_PATH",
        "MODEL_VERSION",
        "UPLOADS_DIR",
        "CORS_ORIGENS",
    ],
)
def test_required_variables_are_enforced(
    monkeypatch: pytest.MonkeyPatch,
    fake_environment: None,
    variable: str,
) -> None:
    """Impede a inicialização das configurações quando um campo obrigatório falta."""
    monkeypatch.delenv(variable)

    with pytest.raises(SettingsConfigurationError) as captured:
        Settings()

    assert variable in str(captured.value)
    assert _FAKE_DATABASE_URL not in str(captured.value)


def test_cors_origins_are_split_and_trimmed(
    fake_environment: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Converte origens CSV em uma lista limpa para o middleware."""
    monkeypatch.setenv(
        "CORS_ORIGENS",
        "http://localhost:5173, https://painel.ficticio.test",
    )

    assert Settings().cors_origens == [
        "http://localhost:5173",
        "https://painel.ficticio.test",
    ]


@pytest.mark.parametrize("origins", ["*", "", " , "])
def test_cors_rejects_wildcard_and_empty_values(
    monkeypatch: pytest.MonkeyPatch,
    fake_environment: None,
    origins: str,
) -> None:
    """Rejeita permissões globais e listas sem nenhuma origem utilizável."""
    monkeypatch.setenv("CORS_ORIGENS", origins)

    with pytest.raises(SettingsConfigurationError) as captured:
        Settings()

    assert "CORS_ORIGENS" in str(captured.value)
    assert _FAKE_DATABASE_URL not in str(captured.value)


def test_threshold_defaults_are_forty_and_seventy(
    fake_environment: None,
) -> None:
    """Usa os limiares previstos quando não há valores no ambiente."""
    settings = Settings()

    assert settings.limiar_atencao == 40
    assert settings.limiar_trocar == 70


@pytest.mark.parametrize(
    ("attention", "replace"),
    [(70, 70), (80, 70), (0, 70), (40, 101)],
)
def test_thresholds_must_be_increasing_and_within_range(
    fake_environment: None,
    monkeypatch: pytest.MonkeyPatch,
    attention: int,
    replace: int,
) -> None:
    """Rejeita limiares fora da escala ou em ordem inconsistente."""
    monkeypatch.setenv("LIMIAR_ATENCAO", str(attention))
    monkeypatch.setenv("LIMIAR_TROCAR", str(replace))

    with pytest.raises(SettingsConfigurationError) as captured:
        Settings()

    assert "LIMIAR_ATENCAO" in str(captured.value)
    assert "LIMIAR_TROCAR" in str(captured.value)
    assert _FAKE_DATABASE_URL not in str(captured.value)


def test_database_url_is_redacted_in_repr_and_validation_errors(
    fake_environment: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mantém a URL mascarada até quando outra configuração é inválida."""
    settings = Settings()
    assert _FAKE_DATABASE_URL not in repr(settings)

    monkeypatch.setenv("CORS_ORIGENS", "*")
    with pytest.raises(SettingsConfigurationError) as captured:
        Settings()

    assert _FAKE_DATABASE_URL not in str(captured.value)
