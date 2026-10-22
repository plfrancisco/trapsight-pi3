"""Confere idempotência, isolamento e correspondência das mídias."""

import hashlib
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.entities import Analise, Armadilha, ModeloArmadilha, Refil
from src.seed_demo import ErroSeedDemo, criar_seed_demo
from training.dataset_sintetico import calcular_percentual_cobertura


def _estado_seed(session: Session) -> tuple[tuple[object, ...], ...]:
    """Serializa as linhas seed para comparação entre execuções."""
    linhas = []
    for identificador in (f"ARM-{indice:03d}" for indice in range(1, 7)):
        armadilha = session.scalars(
            select(Armadilha).where(Armadilha.identificador == identificador)
        ).one()
        linhas.append(
            (
                "armadilha",
                str(armadilha.id),
                armadilha.identificador,
                str(armadilha.modelo_id),
                armadilha.localizacao,
                armadilha.data_instalacao,
                armadilha.criado_em,
            )
        )
        for refil in session.scalars(
            select(Refil)
            .where(Refil.armadilha_id == armadilha.id)
            .order_by(Refil.data_instalacao, Refil.id)
        ):
            linhas.append(
                (
                    "refil",
                    str(armadilha.id),
                    str(refil.id),
                    refil.data_instalacao,
                    refil.data_troca,
                )
            )
            for analise in session.scalars(
                select(Analise)
                .where(Analise.refil_id == refil.id)
                .order_by(Analise.analisado_em, Analise.id)
            ):
                linhas.append(
                    (
                        "analise",
                        str(analise.id),
                        str(refil.id),
                        analise.analisado_em,
                        analise.percentual_coberto,
                        analise.status,
                        analise.caminho_imagem,
                    )
                )
    return tuple(linhas)


def _analises_seed(session: Session) -> list[Analise]:
    """Lista análises pertencentes às seis armadilhas demonstrativas."""
    return list(
        session.scalars(
            select(Analise)
            .join(Refil, Analise.refil_id == Refil.id)
            .join(Armadilha, Refil.armadilha_id == Armadilha.id)
            .where(
                Armadilha.identificador.in_(tuple(f"ARM-{n:03d}" for n in range(1, 7)))
            )
        )
    )


def test_duas_execucoes_produzem_o_mesmo_estado(
    session: Session,
    executar_seed,
    tmp_path: Path,
) -> None:
    """A reexecução substitui somente as linhas e mídias do próprio seed."""
    primeira = executar_seed(session)
    estado_primeiro = _estado_seed(session)
    arquivos = {
        str(analise.id): (
            hashlib.sha256(
                (tmp_path / "uploads" / analise.caminho_imagem).read_bytes()
            ).hexdigest(),
            hashlib.sha256(
                (tmp_path / "uploads" / str(analise.id) / "mascara.png").read_bytes()
            ).hexdigest(),
        )
        for analise in _analises_seed(session)
    }
    primeira.confirmar_arquivos()

    segunda = executar_seed(session)
    assert _estado_seed(session) == estado_primeiro
    assert segunda.quantidade_armadilhas == primeira.quantidade_armadilhas
    assert segunda.quantidade_refis == primeira.quantidade_refis
    assert segunda.quantidade_analises == primeira.quantidade_analises
    segunda.confirmar_arquivos()
    arquivos_depois = {
        str(analise.id): (
            hashlib.sha256(
                (tmp_path / "uploads" / analise.caminho_imagem).read_bytes()
            ).hexdigest(),
            hashlib.sha256(
                (tmp_path / "uploads" / str(analise.id) / "mascara.png").read_bytes()
            ).hexdigest(),
        )
        for analise in _analises_seed(session)
    }
    assert arquivos_depois == arquivos


def test_dados_de_outra_armadilha_e_seus_arquivos_permanecem(
    session: Session,
    executar_seed,
    modelo_stickfly,
    tmp_path: Path,
) -> None:
    """A substituição não toca em linhas ou arquivos fora da propriedade seed."""
    uploads = tmp_path / "uploads"
    analise_id = uuid4()
    armadilha = Armadilha(
        identificador="ARM-OUTRA-SEED-TEST",
        modelo=modelo_stickfly.nome,
        modelo_id=modelo_stickfly.id,
        data_instalacao=None,
    )
    session.add(armadilha)
    session.flush()
    refil = Refil(
        armadilha_id=armadilha.id,
        data_instalacao=date(2026, 10, 1),
    )
    session.add(refil)
    session.flush()
    arquivo_diretorio = uploads / str(analise_id)
    arquivo_diretorio.mkdir(parents=True)
    imagem_path = arquivo_diretorio / "original.png"
    mascara_path = arquivo_diretorio / "mascara.png"
    Image.new("RGB", (10, 10), (1, 2, 3)).save(imagem_path)
    Image.new("L", (10, 10), 0).save(mascara_path)
    analise = Analise(
        id=analise_id,
        refil_id=refil.id,
        analisado_em=datetime(2026, 10, 1, 12, tzinfo=timezone.utc),
        percentual_coberto=Decimal("0.00"),
        status="ok",
        caminho_imagem=f"{analise_id}/original.png",
        modelo_versao="v0.1.0-dev+00000000",
    )
    session.add(analise)
    session.flush()
    imagem_antes = imagem_path.read_bytes()
    mascara_antes = mascara_path.read_bytes()

    resultado = executar_seed(session)
    resultado.confirmar_arquivos()

    assert session.get(Armadilha, armadilha.id) is not None
    assert session.get(Refil, refil.id) is not None
    assert session.get(Analise, analise_id) is not None
    assert imagem_path.read_bytes() == imagem_antes
    assert mascara_path.read_bytes() == mascara_antes


def test_colisao_de_identificador_sem_manifesto_nao_remove_registro(
    session: Session,
    sprites_seed,
    modelo_stickfly: ModeloArmadilha,
    tmp_path: Path,
) -> None:
    """Recusa substituir ARM-001 se o manifesto não provar propriedade do seed."""
    armadilha = Armadilha(
        identificador="ARM-001",
        modelo=modelo_stickfly.nome,
        modelo_id=modelo_stickfly.id,
        localizacao="Inserida manualmente",
        data_instalacao=date(2026, 10, 1),
    )
    session.add(armadilha)
    session.flush()

    with pytest.raises(ErroSeedDemo, match="não consta como dado do seed"):
        criar_seed_demo(
            session,
            diretorio_uploads=tmp_path / "uploads",
            sprites=sprites_seed,
            resolucao=(320, 240),
        )

    assert session.get(Armadilha, armadilha.id) is not None


def test_percentual_persistido_e_medido_na_mascara(
    session: Session,
    executar_seed,
    tmp_path: Path,
) -> None:
    """Cada valor registrado é a medida arredondada da máscara salva."""
    resultado = executar_seed(session)
    resultado.confirmar_arquivos()
    uploads = tmp_path / "uploads"

    for analise in _analises_seed(session):
        diretorio = uploads / str(analise.id)
        caminho_imagem = uploads / analise.caminho_imagem
        assert caminho_imagem.is_file()
        with Image.open(diretorio / "mascara.png") as mascara:
            medido = Decimal(str(calcular_percentual_cobertura(mascara))).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        assert analise.percentual_coberto == medido

    armadilha = session.scalars(
        select(Armadilha).where(Armadilha.identificador == "ARM-001")
    ).one()
    analises_armadilha = list(
        session.scalars(
            select(Analise)
            .join(Refil, Analise.refil_id == Refil.id)
            .where(Refil.armadilha_id == armadilha.id)
        )
    )
    caixas = set()
    for analise in analises_armadilha:
        with Image.open(uploads / str(analise.id) / "mascara.png") as mascara:
            silhueta_placa = mascara.point(lambda valor: 255 if valor > 0 else 0)
            caixas.add(silhueta_placa.getbbox())
    assert len(caixas) == 1

    assert all(
        abs(item.percentual_real - Decimal(str(item.percentual_alvo))) <= Decimal("2")
        for item in resultado.percentuais
    )
