"""Inicialização da aplicação HTTP e de suas configurações de execução."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api import api_router
from src.api.erros import registrar_handlers
from src.config.settings import Settings


def create_app() -> FastAPI:
    """Cria a API com configurações validadas antes de atender requisições."""
    settings = Settings()
    application = FastAPI(
        title="API de monitoramento de armadilhas",
        description=(
            "Serviço para acompanhar armadilhas adesivas e analisar seus refis."
        ),
        docs_url="/docs",
    )
    application.state.settings = settings
    registrar_handlers(application)
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
