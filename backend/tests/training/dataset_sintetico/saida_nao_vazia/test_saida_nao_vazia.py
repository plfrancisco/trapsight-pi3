"""Verifica que a geração não sobrescreve artefatos existentes."""

from pathlib import Path

import pytest


def test_geracao_rejeita_diretorio_de_saida_nao_vazio(
    tmp_path: Path,
    gerar_dataset_teste,
) -> None:
    """Preserva os arquivos quando o diretório de saída já contém dados."""
    saida = tmp_path / "dataset"
    saida.mkdir()
    marcador = saida / "dados-existentes.txt"
    marcador.write_text("preservar", encoding="utf-8")

    with pytest.raises(FileExistsError, match="não está vazio"):
        gerar_dataset_teste(saida, quantidade=1)

    assert marcador.read_text(encoding="utf-8") == "preservar"
