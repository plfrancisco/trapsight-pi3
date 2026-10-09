"""Testes unitários das garantias de caminho do armazenamento de mídia."""

from pathlib import Path

import pytest

from src.services.armazenamento import resolver_caminho_arquivo


def test_resolver_caminho_aceita_arquivo_dentro_da_raiz(tmp_path: Path) -> None:
    """Normaliza um caminho relativo válido para o arquivo armazenado."""
    uploads = tmp_path / "uploads"
    arquivo = uploads / "analise" / "original.jpg"
    arquivo.parent.mkdir(parents=True)
    arquivo.write_bytes(b"imagem")

    resolvido = resolver_caminho_arquivo(uploads, "analise/original.jpg")

    assert resolvido == arquivo.resolve()


@pytest.mark.parametrize("caminho_absoluto", [False, True])
def test_resolver_caminho_rejeita_destino_fora_da_raiz(
    tmp_path: Path,
    caminho_absoluto: bool,
) -> None:
    """Rejeita travessia relativa e caminhos absolutos externos."""
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    externo = tmp_path / "fora.jpg"
    externo.write_bytes(b"privado")
    caminho = externo if caminho_absoluto else Path("../fora.jpg")

    with pytest.raises(ValueError):
        resolver_caminho_arquivo(uploads, caminho)


def test_resolver_caminho_rejeita_symlink_para_fora_da_raiz(
    tmp_path: Path,
) -> None:
    """Resolve symlinks antes de autorizar a abertura do arquivo."""
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    externo = tmp_path / "fora.png"
    externo.write_bytes(b"privado")
    link = uploads / "mascara.png"
    link.symlink_to(externo)

    with pytest.raises(ValueError):
        resolver_caminho_arquivo(uploads, "mascara.png")
