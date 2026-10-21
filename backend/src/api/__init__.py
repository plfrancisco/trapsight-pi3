"""Roteador raiz para endpoints publicados sob o prefixo da API."""

from fastapi import APIRouter

from src.api.rotas.analises import router as analises_router
from src.api.rotas.armadilhas import router as armadilhas_router
from src.api.rotas.auth import router as auth_router
from src.api.rotas.historico import router as historico_router

# A exigência de sessão não é declarada rota a rota: o middleware de proteção
# cobre tudo sob /api (ver src/api/protecao.py), então rota nova nasce protegida.
api_router = APIRouter(prefix="/api")
api_router.include_router(auth_router)
api_router.include_router(analises_router)
api_router.include_router(armadilhas_router)
api_router.include_router(historico_router)
