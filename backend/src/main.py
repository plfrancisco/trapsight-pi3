"""Inicialização da aplicação HTTP e de suas configurações de execução."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api import api_router
from src.api.cabecalhos import CabecalhosDeSegurancaMiddleware
from src.api.erros import registrar_handlers
from src.api.limite_corpo import LimiteCorpoMiddleware
from src.api.protecao import ProtecaoDeSessaoMiddleware, agora_utc
from src.config.database import create_database_engine, create_session_factory
from src.config.settings import Settings
from src.inference.fabrica import criar_inferidor
from src.services.limitador_analises import LimitadorDeAnalises
from src.services.limitador_contas import LimitadorDeContas
from src.services.senhas import ServicoDeSenhas


def create_app() -> FastAPI:
    """Cria a API com configurações validadas antes de atender requisições."""
    settings = Settings()

    inferidor = criar_inferidor(settings)
    engine = create_database_engine(settings.database_url.get_secret_value())

    @asynccontextmanager
    async def lifespan(_application: FastAPI) -> AsyncIterator[None]:
        """Libera as conexões mantidas pelo engine ao encerrar o processo."""
        try:
            yield
        finally:
            engine.dispose()

    application = FastAPI(
        title="API de monitoramento de armadilhas",
        description=(
            "Serviço para acompanhar armadilhas adesivas e analisar seus refis."
        ),
        # Em produção o mapa completo da API não pode ser público.
        docs_url="/docs" if settings.documentacao_habilitada else None,
        redoc_url="/redoc" if settings.documentacao_habilitada else None,
        openapi_url="/openapi.json" if settings.documentacao_habilitada else None,
        lifespan=lifespan,
    )
    application.state.settings = settings
    application.state.engine = engine
    application.state.session_factory = create_session_factory(engine)
    # A proteção de sessão abre a própria sessão; os testes substituem este provedor.
    application.state.provedor_de_sessao = lambda: application.state.session_factory()
    application.state.inferidor = inferidor
    application.state.relogio = agora_utc
    application.state.servico_de_senhas = ServicoDeSenhas(
        memoria_kib=settings.argon2_memoria_kib,
        iteracoes=settings.argon2_iteracoes,
        paralelismo=settings.argon2_paralelismo,
    )
    application.state.limitador_de_analises = LimitadorDeAnalises(
        settings.analises_por_minuto
    )
    application.state.limitador_de_contas = LimitadorDeContas(settings.contas_por_hora)
    # A captura fica antes do CORS para que erros inesperados recebam seus cabeçalhos.
    registrar_handlers(application)
    # A proteção rejeita sem sessão, sem CSRF ou sem origem ANTES de o corpo ser lido.
    application.add_middleware(ProtecaoDeSessaoMiddleware)
    application.add_middleware(LimiteCorpoMiddleware)
    application.add_middleware(CabecalhosDeSegurancaMiddleware)
    # O CORS envolve tudo para que toda rejeição preserve seus cabeçalhos.
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origens,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
        # O cookie de sessão precisa viajar; por isso as origens são sempre explícitas.
        allow_credentials=True,
    )

    @application.get("/healthz", include_in_schema=False)
    def healthz() -> dict[str, str]:
        """Verificação de saúde sem dados sensíveis, fora do prefixo protegido."""
        return {"status": "ok"}

    application.include_router(api_router)
    return application


app = create_app()
