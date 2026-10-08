"""Testes do formato padrão de erro sem conexão com o banco de dados."""

import logging

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from src.api.erros import (
    STATUS_HTTP_POR_CODIGO,
    CodigoErro,
    ErroDeApi,
    registrar_handlers,
    respostas_de_erro,
)


@pytest.fixture
def app() -> FastAPI:
    """Cria uma aplicação isolada com rotas destinadas aos testes de erro."""
    application = FastAPI()

    @application.get("/erro-com-detalhes")
    async def erro_com_detalhes() -> None:
        raise ErroDeApi(
            CodigoErro.ARQUIVO_AUSENTE,
            "Envie uma imagem para continuar.",
            {"campo": "imagem"},
        )

    @application.get("/erro-sem-detalhes")
    async def erro_sem_detalhes() -> None:
        raise ErroDeApi(
            CodigoErro.REFIL_ATIVO_INEXISTENTE,
            "A armadilha não possui refil ativo.",
        )

    @application.get("/validacao")
    async def validar_quantidade(quantidade: int) -> dict[str, int]:
        return {"quantidade": quantidade}

    @application.get("/somente-get")
    async def somente_get() -> dict[str, str]:
        return {"resultado": "ok"}

    @application.get("/http-400")
    async def erro_http_400() -> None:
        raise HTTPException(status_code=400, detail="detalhe interno da requisição")

    @application.get("/http-413")
    async def erro_http_413() -> None:
        raise HTTPException(status_code=413, detail="limite interno")

    @application.get("/http-503")
    async def erro_http_503() -> None:
        raise HTTPException(status_code=503, detail="falha em /srv/segredo.py")

    @application.get("/erro-inesperado")
    async def erro_inesperado() -> None:
        raise RuntimeError("Falha simulada em /srv/interno/config.py")

    @application.get(
        "/documentado",
        responses=respostas_de_erro(
            CodigoErro.ROTA_NAO_ENCONTRADA,
            CodigoErro.ARQUIVO_MUITO_GRANDE,
        ),
    )
    async def rota_documentada() -> dict[str, str]:
        return {"resultado": "ok"}

    registrar_handlers(application)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    return application


@pytest.mark.parametrize(
    ("codigo", "status_http"),
    [
        (CodigoErro.ARMADILHA_NAO_ENCONTRADA, 404),
        (CodigoErro.ANALISE_NAO_ENCONTRADA, 404),
        (CodigoErro.REFIL_ATIVO_INEXISTENTE, 409),
        (CodigoErro.IDENTIFICADOR_DUPLICADO, 409),
        (CodigoErro.ARQUIVO_AUSENTE, 400),
        (CodigoErro.FORMATO_NAO_SUPORTADO, 400),
        (CodigoErro.RESOLUCAO_INSUFICIENTE, 400),
        (CodigoErro.ARQUIVO_MUITO_GRANDE, 413),
        (CodigoErro.VALIDACAO_FALHOU, 422),
        (CodigoErro.REQUISICAO_INVALIDA, 400),
        (CodigoErro.PLACA_NAO_DETECTADA, 500),
        (CodigoErro.FALHA_INFERENCIA, 500),
        (CodigoErro.ROTA_NAO_ENCONTRADA, 404),
        (CodigoErro.METODO_NAO_PERMITIDO, 405),
        (CodigoErro.ERRO_INTERNO, 500),
    ],
)
def test_status_http_corresponde_a_todos_os_codigos(
    codigo: CodigoErro,
    status_http: int,
) -> None:
    """Mantém cada código ligado ao status definido na tabela da API."""
    assert set(STATUS_HTTP_POR_CODIGO) == set(CodigoErro)
    assert STATUS_HTTP_POR_CODIGO[codigo] == status_http
    assert ErroDeApi(codigo, "Mensagem segura.").status_http == status_http


def test_erro_de_api_com_detalhes_responde_no_formato_padrao(app: FastAPI) -> None:
    """Inclui contexto permitido e usa o status associado ao código."""
    response = TestClient(app).get("/erro-com-detalhes")

    assert response.status_code == 400
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {
        "erro": {
            "codigo": "ARQUIVO_AUSENTE",
            "mensagem": "Envie uma imagem para continuar.",
            "detalhes": {"campo": "imagem"},
        }
    }


def test_erro_de_api_omite_detalhes_ausentes(app: FastAPI) -> None:
    """Não serializa detalhes nulos quando nenhum contexto foi informado."""
    response = TestClient(app).get("/erro-sem-detalhes")

    assert response.status_code == 409
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {
        "erro": {
            "codigo": "REFIL_ATIVO_INEXISTENTE",
            "mensagem": "A armadilha não possui refil ativo.",
        }
    }


def test_validacao_422_informa_campo_obrigatorio_ausente(app: FastAPI) -> None:
    """Aponta o campo faltante sem incluir valores de entrada na resposta."""
    response = TestClient(app).get("/validacao")

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["erro"]["codigo"] == "VALIDACAO_FALHOU"
    assert response.json()["erro"]["detalhes"]["campos_invalidos"] == [
        {"campo": "quantidade", "tipo": "missing"}
    ]


def test_validacao_422_omite_valor_de_tipo_incorreto(app: FastAPI) -> None:
    """Informa o tipo da falha de conversão sem ecoar o parâmetro recebido."""
    valor_privado = "valor-privado-4827"
    response = TestClient(app).get("/validacao", params={"quantidade": valor_privado})

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/json")
    assert valor_privado not in response.text
    assert response.json()["erro"]["codigo"] == "VALIDACAO_FALHOU"
    assert response.json()["erro"]["detalhes"]["campos_invalidos"] == [
        {"campo": "quantidade", "tipo": "int_parsing"}
    ]


def test_rota_inexistente_responde_404_no_formato_padrao(app: FastAPI) -> None:
    """Converte a resposta 404 do framework sem expor sua mensagem técnica."""
    response = TestClient(app).get("/rota-inexistente")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {
        "erro": {
            "codigo": "ROTA_NAO_ENCONTRADA",
            "mensagem": "A rota solicitada não foi encontrada.",
        }
    }


@pytest.mark.parametrize(
    ("caminho", "status_http", "codigo", "mensagem"),
    [
        (
            "/http-400",
            400,
            "REQUISICAO_INVALIDA",
            "A requisição não pôde ser processada.",
        ),
        (
            "/http-413",
            413,
            "ARQUIVO_MUITO_GRANDE",
            "O arquivo enviado excede o tamanho permitido.",
        ),
        (
            "/http-503",
            500,
            "ERRO_INTERNO",
            "Ocorreu um erro interno. Tente novamente mais tarde.",
        ),
    ],
)
def test_http_exception_eh_convertida_para_erro_padrao(
    app: FastAPI,
    caminho: str,
    status_http: int,
    codigo: str,
    mensagem: str,
) -> None:
    """Mapeia falhas HTTP sem repassar detalhes internos da exceção."""
    response = TestClient(app).get(caminho)

    assert response.status_code == status_http
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {"erro": {"codigo": codigo, "mensagem": mensagem}}
    assert "detalhe interno" not in response.text
    assert "/srv/segredo.py" not in response.text


def test_metodo_nao_permitido_preserva_cabecalho_allow(app: FastAPI) -> None:
    """Retém a informação de métodos aceitos ao padronizar o erro 405."""
    response = TestClient(app).post("/somente-get")

    assert response.status_code == 405
    assert response.headers["content-type"].startswith("application/json")
    assert response.headers["allow"] == "GET"
    assert response.json() == {
        "erro": {
            "codigo": "METODO_NAO_PERMITIDO",
            "mensagem": "O método HTTP não é permitido para esta rota.",
        }
    }


def test_excecao_inesperada_eh_registrada_e_ocultada(
    app: FastAPI,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Registra traceback no servidor e devolve apenas uma mensagem genérica."""
    caplog.set_level(logging.ERROR, logger="src.api.erros")
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get(
        "/erro-inesperado",
        headers={"Origin": "http://localhost:5173"},
    )

    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/json")
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert response.json() == {
        "erro": {
            "codigo": "ERRO_INTERNO",
            "mensagem": "Ocorreu um erro interno. Tente novamente mais tarde.",
        }
    }
    assert "RuntimeError" in caplog.text
    assert "Traceback (most recent call last)" in caplog.text
    assert "Falha simulada em /srv/interno/config.py" in caplog.text
    assert "Falha simulada em /srv/interno/config.py" not in response.text
    assert "/srv/interno/config.py" not in response.text


def test_erro_inesperado_bloqueia_origem_nao_listada(app: FastAPI) -> None:
    """Não inclui CORS na resposta para uma origem fora da lista permitida."""
    response = TestClient(app, raise_server_exceptions=False).get(
        "/erro-inesperado",
        headers={"Origin": "http://origem-nao-permitida.example"},
    )

    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["erro"]["codigo"] == "ERRO_INTERNO"
    assert "access-control-allow-origin" not in response.headers


def test_openapi_documenta_apenas_erros_declarados_na_rota(app: FastAPI) -> None:
    """Inclui o modelo e somente os status declarados pela operação."""
    response = TestClient(app).get("/openapi.json")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    esquema = response.json()
    assert "RespostaErro" in esquema["components"]["schemas"]
    respostas = esquema["paths"]["/documentado"]["get"]["responses"]
    status_declarados = {"404", "413"}
    status_documentados = {
        status for status in respostas if status.isdigit() and int(status) >= 400
    }
    assert status_documentados == status_declarados
    assert "ROTA_NAO_ENCONTRADA" in respostas["404"]["description"]
    assert "ARQUIVO_MUITO_GRANDE" in respostas["413"]["description"]
    for status_http in status_declarados:
        assert respostas[status_http]["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/RespostaErro"
        }
