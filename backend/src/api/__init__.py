"""Roteador raiz para endpoints publicados sob o prefixo da API."""

from fastapi import APIRouter

from src.api.rotas.armadilhas import router as armadilhas_router

api_router = APIRouter(prefix="/api")
api_router.include_router(armadilhas_router)
