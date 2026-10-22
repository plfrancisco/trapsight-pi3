"""Confere a persistência das mídias nos modos suportados."""

import hashlib
import io
import json
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.entities import Analise
from src.seed_demo import _criar_ids, cenarios_seed
from training.dataset_sintetico import calcular_percentual_cobertura


def _analises_seed(session: Session) -> list[Analise]:
    """Lista as análises determinísticas do seed."""
    ids = tuple(_criar_ids(cenarios_seed())["analises"])
    return list(session.scalars(select(Analise).where(Analise.id.in_(ids))))


def _hashes_das_midias(analises: list[Analise]) -> dict[str, tuple[str, str]]:
    """Calcula hashes das mídias binárias de análises seed."""
    return {
        str(analise.id): (
            hashlib.sha256(bytes(analise.imagem_original or b"")).hexdigest(),
            hashlib.sha256(bytes(analise.mascara or b"")).hexdigest(),
        )
        for analise in analises
    }


def test_database_grava_midias_no_banco_e_manifesto_e_idempotente(
    session: Session,
    executar_seed,
    tmp_path: Path,
) -> None:
    """Armazena imagem e máscara em colunas e reproduz os mesmos bytes."""
    uploads = tmp_path / "uploads"
    primeira = executar_seed(session, "database")
    primeira.confirmar_arquivos()
    analises = _analises_seed(session)
    hashes_primeiros = _hashes_das_midias(analises)

    manifesto_path = uploads / ".seed_demo_manifest.json"
    manifesto = json.loads(manifesto_path.read_text(encoding="utf-8"))
    assert manifesto["storage_backend"] == "database"
    assert {item.name for item in uploads.iterdir()} == {manifesto_path.name}
    assert len(analises) == primeira.quantidade_analises

    for analise in analises:
        assert analise.caminho_imagem == f"{analise.id}/original.png"
        assert analise.imagem_original
        assert analise.mascara
        with Image.open(io.BytesIO(analise.imagem_original)) as imagem:
            imagem.verify()
        with Image.open(io.BytesIO(analise.mascara)) as mascara:
            medido = Decimal(str(calcular_percentual_cobertura(mascara))).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        assert medido == analise.percentual_coberto

    segunda = executar_seed(session, "database")
    segunda.confirmar_arquivos()
    assert _hashes_das_midias(_analises_seed(session)) == hashes_primeiros


def test_manifesto_limpa_midias_ao_alternar_modos(
    session: Session,
    executar_seed,
    tmp_path: Path,
) -> None:
    """Remove arquivos antigos ao alternar do filesystem para o banco."""
    uploads = tmp_path / "uploads"
    resultado_filesystem = executar_seed(session, "filesystem")
    resultado_filesystem.confirmar_arquivos()
    assert sum(1 for item in uploads.iterdir() if item.is_dir()) == 32

    resultado_database = executar_seed(session, "database")
    resultado_database.confirmar_arquivos()

    assert {item.name for item in uploads.iterdir()} == {".seed_demo_manifest.json"}
    assert all(
        analise.imagem_original and analise.mascara
        for analise in _analises_seed(session)
    )

    resultado_filesystem = executar_seed(session, "filesystem")
    resultado_filesystem.confirmar_arquivos()

    assert len([item for item in uploads.iterdir() if item.is_dir()]) == 32
    manifesto = json.loads(
        (uploads / ".seed_demo_manifest.json").read_text(encoding="utf-8")
    )
    assert manifesto["storage_backend"] == "filesystem"
    assert all(
        analise.imagem_original is None and analise.mascara is None
        for analise in _analises_seed(session)
    )
