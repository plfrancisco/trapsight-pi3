"""Verifica a reprodução byte a byte a partir da semente."""

from __future__ import annotations

from pathlib import Path


def test_mesma_semente_produz_arquivos_identicos(
    tmp_path: Path,
    gerar_dataset_teste,
) -> None:
    """Compara byte a byte duas gerações com a mesma configuração."""
    primeira = tmp_path / "primeira"
    segunda = tmp_path / "segunda"
    gerar_dataset_teste(primeira, quantidade=9, semente=77)
    gerar_dataset_teste(segunda, quantidade=9, semente=77)

    arquivos_primeiros = {
        caminho.relative_to(primeira): caminho.read_bytes()
        for caminho in primeira.rglob("*")
        if caminho.is_file()
    }
    arquivos_segundos = {
        caminho.relative_to(segunda): caminho.read_bytes()
        for caminho in segunda.rglob("*")
        if caminho.is_file()
    }
    assert arquivos_primeiros == arquivos_segundos
