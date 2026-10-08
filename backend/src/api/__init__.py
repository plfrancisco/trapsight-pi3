"""Roteador raiz para endpoints publicados sob o prefixo da API."""

from fastapi import APIRouter

api_router = APIRouter(prefix="/api")
