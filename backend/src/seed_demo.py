"""Popula manualmente o banco com os seis cenários de demonstração."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import shutil
import sys
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Sequence
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from src.config.database import create_database_engine, create_session_factory
from src.config.settings import Settings
from src.entities import Analise, Armadilha, ModeloArmadilha, Refil
from src.inference.contrato import validar_versao_semver
from src.inference.status import derivar_status
from training.dataset_sintetico import (
    PESOS_GRUPO_PADRAO,
    RESOLUCAO_PADRAO,
    SpriteCatalogado,
    calcular_percentual_cobertura,
    create_plate_geometry,
    generate_sample,
    load_sprite_catalog,
)

SEMENTE_DEMO = 20261021
IDADE_MAXIMA_DEMO_DIAS = 45.0
RESOLUCAO_DEMO = RESOLUCAO_PADRAO
TOLERANCIA_COBERTURA_PP = 2.0
CODIGO_MODELO = "stickfly-k45"
NOME_MANIFESTO = ".seed_demo_manifest.json"
IDENTIFICADORES = tuple(f"ARM-{indice:03d}" for indice in range(1, 7))
HOSTS_LOCAIS = {"localhost", "127.0.0.1", "::1", "db", "postgres"}
_DOIS_DECIMAIS = Decimal("0.01")


class ErroSeedDemo(Exception):
    """Indica um erro esperado na preparação dos dados de demonstração."""


@dataclass(frozen=True)
class LeituraSpec:
    """Alvo de cobertura em um dia de uso do refil."""

    dia_de_uso: int
    percentual_alvo: float


@dataclass(frozen=True)
class RefilSpec:
    """Ciclo de refil e medições que pertencem a ele."""

    inicio_dias: int
    duracao_dias: int | None
    leituras: tuple[LeituraSpec, ...]


@dataclass(frozen=True)
class ArmadilhaSpec:
    """Dados estáticos e ciclos que compõem um cenário de demonstração."""

    identificador: str
    localizacao: str
    refis: tuple[RefilSpec, ...]


@dataclass(frozen=True)
class RegistroPercentual:
    """Percentual-alvo e percentual medido de uma análise criada."""

    identificador: str
    analisado_em: datetime
    percentual_alvo: float
    percentual_real: Decimal


@dataclass(frozen=True)
class ManifestoSeed:
    """Identificadores usados para reconhecer somente os dados do seed."""

    armadilhas: dict[str, UUID]
    refis: dict[UUID, UUID]
    analises: dict[UUID, UUID]


@dataclass
class OperacaoArquivos:
    """Permite reverter ou concluir a troca das mídias do seed."""

    uploads: Path
    staging: Path
    backup: Path
    manifesto: Path
    diretorios_instalados: list[UUID]
    manifesto_instalado: bool = False
    concluida: bool = False

    def reverter(self) -> None:
        """Restaura as mídias anteriores após uma falha no banco."""
        if self.concluida:
            return
        for analise_id in self.diretorios_instalados:
            destino = self.uploads / str(analise_id)
            if destino.exists():
                shutil.rmtree(destino)
        if self.manifesto_instalado and self.manifesto.exists():
            self.manifesto.unlink()
        if self.backup.exists():
            for item in self.backup.iterdir():
                destino = self.uploads / item.name
                if destino.exists():
                    raise ErroSeedDemo(
                        f"Não foi possível restaurar o arquivo de seed: {destino}."
                    )
                item.replace(destino)
            self.backup.rmdir()
        if self.staging.exists():
            shutil.rmtree(self.staging)
        self.concluida = True

    def confirmar(self) -> None:
        """Remove a cópia de segurança depois do commit do banco."""
        if self.backup.exists():
            shutil.rmtree(self.backup, ignore_errors=True)
        if self.staging.exists():
            shutil.rmtree(self.staging, ignore_errors=True)
        self.concluida = True


@dataclass(frozen=True)
class ResultadoSeedDemo:
    """Contagens e medições produzidas por uma operação do seed."""

    operacao_arquivos: OperacaoArquivos
    quantidade_armadilhas: int
    quantidade_refis: int
    quantidade_analises: int
    percentuais: tuple[RegistroPercentual, ...]

    def reverter_arquivos(self) -> None:
        """Reverte a alteração no volume caso a transação seja cancelada."""
        self.operacao_arquivos.reverter()

    def confirmar_arquivos(self) -> None:
        """Finaliza a alteração no volume depois do commit da transação."""
        self.operacao_arquivos.confirmar()


def data_atual() -> date:
    """Retorna a data local usada como referência dos cenários."""
    return date.today()


def cenarios_seed() -> tuple[ArmadilhaSpec, ...]:
    """Descreve seis ciclos de uso com cronologia relativa à data de execução."""
    return (
        ArmadilhaSpec(
            "ARM-001",
            "Cozinha - área de preparo",
            (
                RefilSpec(
                    -32,
                    None,
                    tuple(
                        LeituraSpec(dia, percentual)
                        for dia, percentual in zip(
                            range(2, 33, 3),
                            (10, 17, 24, 31, 38, 45, 52, 58, 64, 72.5, 78),
                            strict=True,
                        )
                    ),
                ),
            ),
        ),
        ArmadilhaSpec(
            "ARM-002",
            "Depósito - corredor central",
            (
                RefilSpec(
                    -20,
                    None,
                    tuple(
                        LeituraSpec(dia, percentual)
                        for dia, percentual in zip(
                            range(2, 21, 3),
                            (5.5, 13.75, 22, 30.25, 38.5, 46.75, 55),
                            strict=True,
                        )
                    ),
                ),
            ),
        ),
        ArmadilhaSpec(
            "ARM-003",
            "Refeitório - entrada",
            (
                RefilSpec(
                    -6,
                    None,
                    (LeituraSpec(3, 7), LeituraSpec(6, 12)),
                ),
            ),
        ),
        ArmadilhaSpec(
            "ARM-004",
            "Estoque - perto da doca",
            (
                RefilSpec(
                    -98,
                    38,
                    (LeituraSpec(3, 14), LeituraSpec(18, 40), LeituraSpec(33, 65)),
                ),
                RefilSpec(
                    -60,
                    45,
                    (
                        LeituraSpec(3, 12),
                        LeituraSpec(18, 32),
                        LeituraSpec(33, 55),
                        LeituraSpec(42, 68),
                    ),
                ),
                RefilSpec(
                    -15,
                    None,
                    (
                        LeituraSpec(3, 8),
                        LeituraSpec(6, 12),
                        LeituraSpec(9, 18),
                        LeituraSpec(12, 22),
                        LeituraSpec(15, 27),
                    ),
                ),
            ),
        ),
        ArmadilhaSpec(
            "ARM-005",
            "Câmara fria - área externa",
            (RefilSpec(-7, None, ()),),
        ),
        ArmadilhaSpec(
            "ARM-006",
            "Recebimento - parede norte",
            (RefilSpec(-38, 38, ()),),
        ),
    )


def carregar_sprites_do_ambiente() -> tuple[SpriteCatalogado, ...]:
    """Carrega o catálogo externo indicado por TRAPSIGHT_TRAINING_DATA_DIR."""
    valor = os.environ.get("TRAPSIGHT_TRAINING_DATA_DIR")
    if not valor or not valor.strip():
        raise ErroSeedDemo(
            "Defina TRAPSIGHT_TRAINING_DATA_DIR para o banco de sprites externo; "
            "prepare-o com training.coletar_inaturalist e training.preparar_sprites."
        )
    raiz = Path(valor).expanduser().resolve()
    candidatos = (raiz / "sprites", raiz)
    diretorio = next(
        (
            candidato
            for candidato in candidatos
            if (candidato / "manifest.json").is_file()
        ),
        None,
    )
    if diretorio is None:
        raise ErroSeedDemo(
            "O banco de sprites não contém manifest.json. Execute "
            "training.preparar_sprites no diretório externo indicado por "
            "TRAPSIGHT_TRAINING_DATA_DIR."
        )
    raiz_repositorio = Path(__file__).resolve().parents[2]
    if diretorio.is_relative_to(raiz_repositorio):
        raise ErroSeedDemo(
            "TRAPSIGHT_TRAINING_DATA_DIR deve apontar para um banco fora do repositório."
        )
    try:
        return load_sprite_catalog(diretorio)
    except (OSError, ValueError) as erro:
        raise ErroSeedDemo(
            f"Não foi possível carregar o banco de sprites: {erro}"
        ) from erro


def criar_seed_demo(
    session: Session,
    *,
    diretorio_uploads: str | Path,
    sprites: tuple[SpriteCatalogado, ...] | None = None,
    modelo_versao: str = "v0.1.0-dev+00000000",
    limiar_atencao: Decimal = Decimal("40"),
    limiar_trocar: Decimal = Decimal("70"),
    resolucao: tuple[int, int] = RESOLUCAO_DEMO,
) -> ResultadoSeedDemo:
    """Cria os seis cenários e suas mídias na transação atual.

    A sessão permanece sem commit para que o comando chamador possa confirmar o
    banco antes de descartar a cópia de segurança dos arquivos.
    """
    catalogo = sprites if sprites is not None else carregar_sprites_do_ambiente()
    hoje = data_atual()
    instante_criacao = datetime.combine(hoje, time(12), timezone.utc)
    try:
        modelo = session.scalars(
            select(ModeloArmadilha).where(ModeloArmadilha.codigo == CODIGO_MODELO)
        ).one_or_none()
    except ProgrammingError as erro:
        raise ErroSeedDemo(
            "Não foi possível consultar o catálogo StickFly K-45. Aplique as "
            "migrations até 0004_catalogo_modelos_armadilha."
        ) from erro
    if modelo is None or not modelo.ativo:
        raise ErroSeedDemo(
            "O modelo ativo stickfly-k45 não foi encontrado. Aplique a migration "
            "0004_catalogo_modelos_armadilha antes de executar o seed."
        )

    base = _criar_ids(cenarios_seed())
    manifesto_previo = _ler_manifesto(diretorio_uploads)
    _validar_propriedade_no_banco(session, manifesto_previo, base)
    staging, dados_analises, percentuais = _gerar_midias(
        catalogo,
        base,
        hoje,
        instante_criacao,
        diretorio_uploads,
        resolucao,
    )
    manifesto_novo = _montar_manifesto(base, hoje, percentuais)
    (staging / NOME_MANIFESTO).write_text(
        json.dumps(manifesto_novo, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    try:
        operacao_arquivos = _instalar_midias(
            diretorio_uploads,
            staging,
            manifesto_previo,
            manifesto_novo,
        )
        _substituir_registros(
            session,
            manifesto_previo,
            base,
            dados_analises,
            modelo,
            instante_criacao,
            modelo_versao,
            limiar_atencao,
            limiar_trocar,
        )
    except Exception:
        if "operacao_arquivos" in locals():
            operacao_arquivos.reverter()
        elif staging.exists():
            shutil.rmtree(staging)
        raise

    return ResultadoSeedDemo(
        operacao_arquivos=operacao_arquivos,
        quantidade_armadilhas=len(base["armadilhas"]),
        quantidade_refis=len(base["refis"]),
        quantidade_analises=len(dados_analises),
        percentuais=tuple(percentuais),
    )


def _criar_ids(cenarios: tuple[ArmadilhaSpec, ...]) -> dict[str, object]:
    """Gera IDs estáveis para armadilhas, refis e análises."""
    armadilhas: dict[str, UUID] = {}
    refis: dict[UUID, tuple[UUID, RefilSpec]] = {}
    analises: dict[UUID, tuple[UUID, ArmadilhaSpec, RefilSpec, LeituraSpec, int]] = {}
    for cenario in cenarios:
        armadilha_id = _uuid_deterministico("armadilha", cenario.identificador)
        armadilhas[cenario.identificador] = armadilha_id
        indice_analise = 0
        for indice_refil, refil_spec in enumerate(cenario.refis):
            refil_id = _uuid_deterministico(
                "refil", cenario.identificador, str(indice_refil)
            )
            refis[refil_id] = (armadilha_id, refil_spec)
            for leitura in refil_spec.leituras:
                analise_id = _uuid_deterministico(
                    "analise", cenario.identificador, str(indice_analise)
                )
                analises[analise_id] = (
                    refil_id,
                    cenario,
                    refil_spec,
                    leitura,
                    indice_analise,
                )
                indice_analise += 1
    return {"armadilhas": armadilhas, "refis": refis, "analises": analises}


def _uuid_deterministico(tipo: str, *partes: str) -> UUID:
    """Retorna um UUID estável para o mesmo registro lógico do seed."""
    nome = ":".join((str(SEMENTE_DEMO), tipo, *partes))
    return uuid5(NAMESPACE_URL, f"trapsight-seed-demo:{nome}")


def _ler_manifesto(diretorio_uploads: str | Path) -> ManifestoSeed | None:
    """Lê o registro de propriedade sem seguir links simbólicos."""
    raiz = Path(diretorio_uploads).resolve()
    caminho = raiz / NOME_MANIFESTO
    if not caminho.exists():
        return None
    if caminho.is_symlink() or not caminho.is_file():
        raise ErroSeedDemo(f"O manifesto do seed não é um arquivo regular: {caminho}.")
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        armadilhas = {
            identificador: UUID(valor)
            for identificador, valor in dados["armadilhas"].items()
        }
        refis = {UUID(chave): UUID(valor) for chave, valor in dados["refis"].items()}
        analises = {
            UUID(chave): UUID(valor) for chave, valor in dados["analises"].items()
        }
        if (
            dados.get("formato") != 1
            or set(armadilhas) != set(IDENTIFICADORES)
            or len(set(armadilhas.values())) != len(armadilhas)
        ):
            raise ValueError("estrutura inesperada")
    except (
        AttributeError,
        KeyError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as erro:
        raise ErroSeedDemo(
            f"O manifesto do seed está inválido; nada foi removido: {caminho}."
        ) from erro

    for analise_id in analises:
        diretorio = raiz / str(analise_id)
        if diretorio.exists():
            _validar_diretorio_analise(diretorio)
    return ManifestoSeed(armadilhas, refis, analises)


def _validar_propriedade_no_banco(
    session: Session,
    manifesto: ManifestoSeed | None,
    novos_ids: dict[str, object],
) -> None:
    """Impede substituição de registros que não estejam no manifesto do seed."""
    ids_armadilhas = set() if manifesto is None else set(manifesto.armadilhas.values())
    ids_refis = set() if manifesto is None else set(manifesto.refis)
    ids_analises = set() if manifesto is None else set(manifesto.analises)
    codigos = set(IDENTIFICADORES)
    armadilhas_existentes = list(
        session.scalars(select(Armadilha).where(Armadilha.identificador.in_(codigos)))
    )
    propriedade_por_codigo = {} if manifesto is None else manifesto.armadilhas
    for armadilha in armadilhas_existentes:
        if propriedade_por_codigo.get(armadilha.identificador) != armadilha.id:
            raise ErroSeedDemo(
                f"{armadilha.identificador} já existe e não consta como dado do seed; "
                "nenhum registro foi alterado."
            )

    if ids_armadilhas:
        armadilhas_seed = list(
            session.scalars(select(Armadilha).where(Armadilha.id.in_(ids_armadilhas)))
        )
        for armadilha in armadilhas_seed:
            if propriedade_por_codigo.get(armadilha.identificador) != armadilha.id:
                raise ErroSeedDemo(
                    "O manifesto não corresponde às armadilhas do banco."
                )

        refis_existentes = list(
            session.scalars(select(Refil).where(Refil.armadilha_id.in_(ids_armadilhas)))
        )
        for refil in refis_existentes:
            if (
                manifesto is None
                or refil.id not in ids_refis
                or manifesto.refis.get(refil.id) != refil.armadilha_id
            ):
                raise ErroSeedDemo(
                    "Há um refil sem registro de propriedade ligado a uma armadilha "
                    "do seed; nada foi removido."
                )

        refis_por_id = list(
            session.scalars(select(Refil).where(Refil.id.in_(ids_refis)))
        )
        for refil in refis_por_id:
            if (
                manifesto is None
                or manifesto.refis.get(refil.id) != refil.armadilha_id
                or refil.armadilha_id not in ids_armadilhas
            ):
                raise ErroSeedDemo(
                    "O manifesto associa um refil a uma armadilha que não pertence "
                    "ao seed; nada foi removido."
                )

        analises_existentes = list(
            session.scalars(
                select(Analise)
                .join(Refil, Analise.refil_id == Refil.id)
                .where(Refil.armadilha_id.in_(ids_armadilhas))
            )
        )
        for analise in analises_existentes:
            if (
                manifesto is None
                or analise.id not in ids_analises
                or manifesto.analises.get(analise.id) != analise.refil_id
            ):
                raise ErroSeedDemo(
                    "Há uma análise sem registro de propriedade ligada a uma armadilha "
                    "do seed; nada foi removido."
                )

        analises_por_id = list(
            session.scalars(select(Analise).where(Analise.id.in_(ids_analises)))
        )
        for analise in analises_por_id:
            if (
                manifesto is None
                or manifesto.analises.get(analise.id) != analise.refil_id
                or analise.refil_id not in ids_refis
            ):
                raise ErroSeedDemo(
                    "O manifesto associa uma análise a um refil que não pertence "
                    "ao seed; nada foi removido."
                )

    _validar_colisoes_de_ids(
        session, novos_ids, ids_armadilhas, ids_refis, ids_analises
    )


def _validar_colisoes_de_ids(
    session: Session,
    novos_ids: dict[str, object],
    armadilhas_proprias: set[UUID],
    refis_proprios: set[UUID],
    analises_proprias: set[UUID],
) -> None:
    """Rejeita UUID determinístico já usado por dados fora do seed."""
    ids_armadilhas = set(novos_ids["armadilhas"].values())
    ids_refis = set(novos_ids["refis"])
    ids_analises = set(novos_ids["analises"])
    for classe, novos, proprios in (
        (Armadilha, ids_armadilhas, armadilhas_proprias),
        (Refil, ids_refis, refis_proprios),
        (Analise, ids_analises, analises_proprias),
    ):
        encontrados = set(
            session.scalars(select(classe.id).where(classe.id.in_(novos)))
        )
        if encontrados - proprios:
            raise ErroSeedDemo(
                "Um identificador determinístico do seed já pertence a outro registro."
            )


def _gerar_midias(
    sprites: tuple[SpriteCatalogado, ...],
    ids: dict[str, object],
    hoje: date,
    instante_criacao: datetime,
    diretorio_uploads: str | Path,
    resolucao: tuple[int, int],
) -> tuple[Path, list[dict[str, object]], list[RegistroPercentual]]:
    """Gera cenas convergidas e seus pares de arquivos em uma pasta temporária."""
    uploads = Path(diretorio_uploads).resolve()
    uploads.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".seed-demo-stage-", dir=uploads))
    dados_analises: list[dict[str, object]] = []
    percentuais: list[RegistroPercentual] = []
    try:
        for analise_id, (refil_id, cenario, refil_spec, leitura, indice) in ids[
            "analises"
        ].items():
            semente_trap = _semente_armadilha(cenario.identificador)
            geometria = create_plate_geometry(
                resolucao,
                random.Random(semente_trap ^ 0xBACE),
            )
            rng = random.Random(semente_trap ^ ((indice + 1) * 0x9E3779B1))
            rng_base = random.Random(semente_trap ^ 0xC4E)
            idade_simulada = float(leitura.dia_de_uso)
            amostra = generate_sample(
                sprites,
                leitura.percentual_alvo,
                idade_simulada,
                IDADE_MAXIMA_DEMO_DIAS,
                rng,
                resolucao=resolucao,
                geometria_placa=geometria,
                rng_base=rng_base,
            )
            percentual_medido = calcular_percentual_cobertura(amostra.mascara)
            if (
                not amostra.alvo_atingido
                or abs(percentual_medido - leitura.percentual_alvo)
                > TOLERANCIA_COBERTURA_PP
            ):
                raise ErroSeedDemo(
                    f"A imagem de {cenario.identificador} não convergiu para "
                    f"{leitura.percentual_alvo:.2f}% (medido {percentual_medido:.2f}%)."
                )
            percentual_decimal = Decimal(str(percentual_medido)).quantize(
                _DOIS_DECIMAIS,
                rounding=ROUND_HALF_UP,
            )
            diretorio_analise = staging / str(analise_id)
            diretorio_analise.mkdir()
            amostra.imagem.save(diretorio_analise / "original.png", format="PNG")
            amostra.mascara.save(diretorio_analise / "mascara.png", format="PNG")
            data_refil = hoje + timedelta(days=refil_spec.inicio_dias)
            analisado_em = datetime.combine(
                data_refil + timedelta(days=leitura.dia_de_uso),
                time(12),
                timezone.utc,
            )
            dados_analises.append(
                {
                    "id": analise_id,
                    "refil_id": refil_id,
                    "analisado_em": analisado_em,
                    "percentual_coberto": percentual_decimal,
                    "caminho_imagem": f"{analise_id}/original.png",
                }
            )
            percentuais.append(
                RegistroPercentual(
                    cenario.identificador,
                    analisado_em,
                    leitura.percentual_alvo,
                    percentual_decimal,
                )
            )
    except Exception:
        shutil.rmtree(staging)
        raise
    return staging, dados_analises, percentuais


def _semente_armadilha(identificador: str) -> int:
    """Deriva uma semente estável sem depender do hash aleatório do processo."""
    return _uuid_deterministico("placa", identificador).int & ((1 << 64) - 1)


def _montar_manifesto(
    ids: dict[str, object],
    hoje: date,
    percentuais: list[RegistroPercentual],
) -> dict[str, object]:
    """Monta o manifesto de propriedade e o resumo das mídias geradas."""
    return {
        "formato": 1,
        "semente": SEMENTE_DEMO,
        "data_execucao": hoje.isoformat(),
        "modelo_codigo": CODIGO_MODELO,
        "pesos_grupo": dict(sorted(PESOS_GRUPO_PADRAO.items())),
        "armadilhas": {chave: str(valor) for chave, valor in ids["armadilhas"].items()},
        "refis": {str(chave): str(valor[0]) for chave, valor in ids["refis"].items()},
        "analises": {
            str(chave): str(valor[0]) for chave, valor in ids["analises"].items()
        },
        "percentuais": [
            {
                "identificador": item.identificador,
                "analisado_em": item.analisado_em.isoformat(),
                "alvo": item.percentual_alvo,
                "real": float(item.percentual_real),
            }
            for item in percentuais
        ],
    }


def _instalar_midias(
    diretorio_uploads: str | Path,
    staging: Path,
    manifesto_previo: ManifestoSeed | None,
    manifesto_novo: dict[str, object],
) -> OperacaoArquivos:
    """Troca somente pastas de análises pertencentes a uma execução anterior."""
    uploads = Path(diretorio_uploads).resolve()
    uploads.mkdir(parents=True, exist_ok=True)
    manifesto = uploads / NOME_MANIFESTO
    backup = Path(tempfile.mkdtemp(prefix=".seed-demo-backup-", dir=uploads))
    operacao = OperacaoArquivos(
        uploads,
        staging,
        backup,
        manifesto,
        [],
    )
    antigos = set() if manifesto_previo is None else set(manifesto_previo.analises)
    novos = {UUID(valor) for valor in manifesto_novo["analises"]}
    try:
        if manifesto.exists():
            if manifesto.is_symlink() or not manifesto.is_file():
                raise ErroSeedDemo(
                    "O manifesto de propriedade não é um arquivo regular."
                )
            manifesto.replace(backup / NOME_MANIFESTO)
        for analise_id in antigos:
            origem = uploads / str(analise_id)
            if origem.exists():
                _validar_diretorio_analise(origem)
                origem.replace(backup / str(analise_id))
        for analise_id in novos:
            destino = uploads / str(analise_id)
            if destino.exists():
                raise ErroSeedDemo(
                    f"O diretório de upload já existe e não pertence ao seed: {destino}."
                )
            (staging / str(analise_id)).replace(destino)
            operacao.diretorios_instalados.append(analise_id)
        (staging / NOME_MANIFESTO).replace(manifesto)
        operacao.manifesto_instalado = True
    except Exception:
        operacao.reverter()
        raise
    return operacao


def _validar_diretorio_analise(diretorio: Path) -> None:
    """Exige que uma mídia pertencente ao seed contenha apenas imagem e máscara."""
    if diretorio.is_symlink() or not diretorio.is_dir():
        raise ErroSeedDemo(
            f"A pasta da análise não é um diretório regular: {diretorio}."
        )
    itens = list(diretorio.iterdir())
    if {item.name for item in itens} != {"original.png", "mascara.png"} or any(
        item.is_symlink() or not item.is_file() for item in itens
    ):
        raise ErroSeedDemo(
            f"A pasta da análise contém arquivos não reconhecidos; nada foi removido: "
            f"{diretorio}."
        )


def _substituir_registros(
    session: Session,
    manifesto_previo: ManifestoSeed | None,
    ids: dict[str, object],
    dados_analises: list[dict[str, object]],
    modelo: ModeloArmadilha,
    instante_criacao: datetime,
    modelo_versao: str,
    limiar_atencao: Decimal,
    limiar_trocar: Decimal,
) -> None:
    """Substitui somente linhas listadas no manifesto de propriedade anterior."""
    if manifesto_previo is not None:
        for analise in session.scalars(
            select(Analise).where(Analise.id.in_(manifesto_previo.analises))
        ):
            session.delete(analise)
        for refil in session.scalars(
            select(Refil).where(Refil.id.in_(manifesto_previo.refis))
        ):
            session.delete(refil)
        for armadilha in session.scalars(
            select(Armadilha).where(
                Armadilha.id.in_(manifesto_previo.armadilhas.values())
            )
        ):
            session.delete(armadilha)
        session.flush()

    especificacoes = {item.identificador: item for item in cenarios_seed()}
    for identificador, armadilha_id in ids["armadilhas"].items():
        cenario = especificacoes[identificador]
        primeira_data = min(
            instante_criacao.date() + timedelta(days=refil.inicio_dias)
            for refil in cenario.refis
        )
        armadilha = Armadilha(
            id=armadilha_id,
            identificador=identificador,
            modelo=modelo.nome,
            modelo_id=modelo.id,
            localizacao=cenario.localizacao,
            data_instalacao=primeira_data,
            criado_em=instante_criacao,
        )
        session.add(armadilha)

    for refil_id, (armadilha_id, refil_spec) in ids["refis"].items():
        data_instalacao = instante_criacao.date() + timedelta(
            days=refil_spec.inicio_dias
        )
        refil = Refil(
            id=refil_id,
            armadilha_id=armadilha_id,
            data_instalacao=data_instalacao,
            data_troca=(
                None
                if refil_spec.duracao_dias is None
                else data_instalacao + timedelta(days=refil_spec.duracao_dias)
            ),
            criado_em=instante_criacao,
        )
        session.add(refil)

    for dados in dados_analises:
        percentual = dados["percentual_coberto"]
        status = derivar_status(percentual, limiar_atencao, limiar_trocar)
        session.add(
            Analise(
                id=dados["id"],
                refil_id=dados["refil_id"],
                analisado_em=dados["analisado_em"],
                percentual_coberto=percentual,
                status=status.value,
                caminho_imagem=dados["caminho_imagem"],
                modelo_versao=modelo_versao,
                criado_em=instante_criacao,
            )
        )
    session.flush()


def _modelo_versao(settings: Settings) -> str:
    """Anexa o hash dos pesos configurados ou o hash nulo do inferidor stub."""
    caminho_pesos = Path(settings.model_weights_path)
    if caminho_pesos.is_file():
        with caminho_pesos.open("rb") as arquivo:
            hash_pesos = hashlib.file_digest(arquivo, "sha256").hexdigest()[:8]
    else:
        hash_pesos = "00000000"
    validar_versao_semver(settings.model_version)
    return f"{settings.model_version}+{hash_pesos}"


def destino_banco(database_url: str | URL) -> tuple[str, str, str]:
    """Retorna host, nome do banco e ambiente sem expor credenciais."""
    try:
        url = database_url if isinstance(database_url, URL) else make_url(database_url)
        porta = f":{url.port}" if url.port is not None else ""
    except (TypeError, ValueError):
        raise ErroSeedDemo("DATABASE_URL inválida; verifique a configuração.") from None
    host = url.host or "socket local"
    destino = f"{host}{porta}/{url.database or 'sem banco'}"
    return host, url.database or "", destino


def validar_ambiente(
    database_url: str | URL,
    ambiente: str,
    confirmar_ambiente: bool,
) -> str:
    """Bloqueia ambientes não locais sem confirmação explícita."""
    host, _, destino = destino_banco(database_url)
    remoto = host.lower() not in HOSTS_LOCAIS
    requer_confirmacao = ambiente != "desenvolvimento" or remoto
    if requer_confirmacao and not confirmar_ambiente:
        raise ErroSeedDemo(
            f"Destino do banco: {destino}. O seed exige a flag "
            "--confirmar-ambiente fora do desenvolvimento local."
        )
    return destino


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.seed_demo",
        description=__doc__,
    )
    parser.add_argument(
        "--confirmar-ambiente",
        action="store_true",
        help="permite executar em banco fora do desenvolvimento local",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Executa explicitamente o seed e confirma banco e arquivos em conjunto."""
    args = _parser().parse_args(argv)
    resultado: ResultadoSeedDemo | None = None
    engine = None
    try:
        settings = Settings()
        destino = validar_ambiente(
            settings.database_url.get_secret_value(),
            os.environ.get("AMBIENTE", "desenvolvimento").strip().lower(),
            args.confirmar_ambiente,
        )
        print(f"Destino do banco: {destino}")
        if settings.storage_backend != "filesystem":
            raise ErroSeedDemo(
                "O seed grava as mídias em UPLOADS_DIR; configure "
                "STORAGE_BACKEND=filesystem."
            )
        sprites = carregar_sprites_do_ambiente()
        engine = create_database_engine(settings.database_url.get_secret_value())
        with create_session_factory(engine)() as session:
            try:
                resultado = criar_seed_demo(
                    session,
                    diretorio_uploads=settings.uploads_dir,
                    sprites=sprites,
                    modelo_versao=_modelo_versao(settings),
                    limiar_atencao=Decimal(settings.limiar_atencao),
                    limiar_trocar=Decimal(settings.limiar_trocar),
                )
                session.commit()
            except Exception:
                session.rollback()
                if resultado is not None:
                    resultado.reverter_arquivos()
                raise
        resultado.confirmar_arquivos()
    except ErroSeedDemo as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 1
    except Exception as erro:
        if resultado is not None:
            resultado.reverter_arquivos()
        print(f"Erro ao criar os dados de demonstração: {erro}", file=sys.stderr)
        return 1
    finally:
        if engine is not None:
            engine.dispose()

    assert resultado is not None
    print(
        f"Seed concluído: {resultado.quantidade_armadilhas} armadilhas, "
        f"{resultado.quantidade_refis} refis e "
        f"{resultado.quantidade_analises} análises."
    )
    print("Armadilha\tData\tAlvo (%)\tRegistrado (%)")
    for percentual in resultado.percentuais:
        print(
            f"{percentual.identificador}\t"
            f"{percentual.analisado_em.date().isoformat()}\t"
            f"{percentual.percentual_alvo:.2f}\t"
            f"{percentual.percentual_real:.2f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
