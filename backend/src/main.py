"""Inicialização da aplicação HTTP e de suas configurações de execução."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api import api_router
from src.api.erros import registrar_handlers
from src.api.limite_corpo import LimiteCorpoMiddleware
from src.config.database import create_database_engine, create_session_factory
from src.config.settings import Settings
from src.inference.fabrica import criar_inferidor


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
        docs_url="/docs",
        lifespan=lifespan,
    )
    application.state.settings = settings
    application.state.engine = engine
    application.state.session_factory = create_session_factory(engine)
    application.state.inferidor = inferidor
    # A captura fica antes do CORS para que erros inesperados recebam seus cabeçalhos.
    registrar_handlers(application)
    # O CORS envolve o limite para que a rejeição antecipada preserve seus cabeçalhos.
    application.add_middleware(LimiteCorpoMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origens,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["Content-Type"],
        allow_credentials=False,
    )
    application.include_router(api_router)
    return application


app = create_app()
