"""Testes de integração das entidades e dos repositórios no PostgreSQL."""

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.entities import Analise, Armadilha, Base, Refil, StatusAnalise
from src.repositories import (
    AnaliseRepository,
    ArmadilhaRepository,
    DataTrocaInvalida,
    ErroDeDominio,
    IdentificadorDuplicado,
    RefilAtivoExistente,
    RefilJaEncerrado,
    RefilRepository,
)


def test_armadilha_create_get_list_and_update(session: Session) -> None:
    """Cobre criação, consultas, listagem e atualização parcial de armadilha."""
    repository = ArmadilhaRepository(session)
    armadilha = repository.create(
        identificador="ARM-001",
        modelo="StickFly K-45",
        localizacao="Recebimento",
        data_instalacao=date(2026, 9, 1),
    )
    outra = repository.create(identificador="ARM-002")

    assert armadilha.id is not None
    assert repository.get_by_id(armadilha.id) is armadilha
    assert repository.get_by_identificador("ARM-001") is armadilha
    assert repository.get_by_identificador("ausente") is None
    assert repository.list_all() == [armadilha, outra]

    atualizada = repository.update(
        armadilha.id,
        identificador="ARM-003",
        modelo=None,
        localizacao="Expedição",
    )
    assert atualizada is armadilha
    assert armadilha.identificador == "ARM-003"
    assert armadilha.modelo is None
    assert armadilha.localizacao == "Expedição"
    assert repository.update(outra.id, localizacao="Laboratório") is outra
    assert repository.update(outra.id, modelo="StickFly K-46") is outra
    assert repository.update(outra.id, identificador="ARM-004") is outra
    assert repository.update(UUID(int=0), identificador="x") is None


def test_duplicate_identifier_raises_domain_exception(session: Session) -> None:
    """Esconde detalhes da constraint e do driver ao detectar código duplicado."""
    repository = ArmadilhaRepository(session)
    repository.create(identificador="ARM-001")

    with pytest.raises(IdentificadorDuplicado) as captured:
        repository.create(identificador="ARM-001")

    assert "constraint" not in str(captured.value).lower()
    assert "sqlalchemy" not in str(captured.value).lower()


def test_refil_lifecycle_and_closed_order(session: Session) -> None:
    """Busca ciclos ativos, encerra um refil e ordena os encerrados no tempo."""
    armadilha = ArmadilhaRepository(session).create(identificador="ARM-001")
    repository = RefilRepository(session)
    first = repository.create(
        armadilha_id=armadilha.id,
        data_instalacao=date(2026, 1, 1),
        data_troca=date(2026, 2, 1),
    )
    second = repository.create(
        armadilha_id=armadilha.id,
        data_instalacao=date(2026, 2, 2),
        data_troca=date(2026, 3, 1),
    )
    active = repository.create(
        armadilha_id=armadilha.id,
        data_instalacao=date(2026, 3, 2),
    )

    assert repository.get_by_id(active.id) is active
    assert repository.get_active_for_armadilha(armadilha.id) is active
    assert repository.list_closed_for_armadilha(armadilha.id) == [first, second]

    encerrado = repository.close(active.id, date(2026, 4, 2))
    assert encerrado is active
    assert active.data_troca == date(2026, 4, 2)
    assert repository.get_active_for_armadilha(armadilha.id) is None
    assert repository.list_closed_for_armadilha(armadilha.id) == [first, second, active]
    assert repository.close(UUID(int=0), date(2026, 4, 3)) is None


def test_analise_queries_order_and_limit(session: Session) -> None:
    """Confere consultas cronológicas por refil e pelo conjunto da armadilha."""
    armadilha = ArmadilhaRepository(session).create(identificador="ARM-001")
    refil_repo = RefilRepository(session)
    first_refil = refil_repo.create(
        armadilha_id=armadilha.id,
        data_instalacao=date(2026, 1, 1),
    )
    refil_repo.close(first_refil.id, date(2026, 1, 31))
    second_refil = refil_repo.create(
        armadilha_id=armadilha.id,
        data_instalacao=date(2026, 2, 1),
    )
    repository = AnaliseRepository(session)
    first = repository.create(
        refil_id=first_refil.id,
        analisado_em=datetime(2026, 1, 3, tzinfo=timezone.utc),
        percentual_coberto=Decimal("30.00"),
        status=StatusAnalise.OK,
        caminho_imagem="analises/primeira.jpg",
        modelo_versao="v1.0.0+12345678",
    )
    latest_first = repository.create(
        refil_id=first_refil.id,
        analisado_em=datetime(2026, 1, 5, tzinfo=timezone.utc),
        percentual_coberto=Decimal("45.00"),
        status=StatusAnalise.ATENCAO,
        caminho_imagem="analises/segunda.jpg",
        modelo_versao="v1.0.0+12345678",
    )
    middle = repository.create(
        refil_id=second_refil.id,
        analisado_em=datetime(2026, 1, 4, tzinfo=timezone.utc),
        percentual_coberto=Decimal("70.00"),
        status=StatusAnalise.ATENCAO,
        caminho_imagem="analises/terceira.jpg",
        modelo_versao="v1.0.0+12345678",
    )
    latest_refil = repository.create(
        refil_id=first_refil.id,
        analisado_em=datetime(2026, 1, 7, tzinfo=timezone.utc),
        percentual_coberto=Decimal("82.00"),
        status=StatusAnalise.TROCAR,
        caminho_imagem="analises/quarta.jpg",
        modelo_versao="v1.0.0+12345678",
    )

    assert repository.get_by_id(first.id) is first
    assert repository.get_by_id(UUID(int=0)) is None
    assert repository.get_latest_for_refil(first_refil.id) is latest_refil
    assert repository.list_by_refil(first_refil.id) == [
        first,
        latest_first,
        latest_refil,
    ]
    assert repository.list_by_refil(first_refil.id, limit=2) == [
        latest_first,
        latest_refil,
    ]
    assert repository.list_by_refil(first_refil.id, limit=None) == [
        first,
        latest_first,
        latest_refil,
    ]
    assert repository.list_by_armadilha(armadilha.id) == [
        first,
        middle,
        latest_first,
        latest_refil,
    ]
    assert repository.list_by_armadilha(armadilha.id, limit=2) == [
        latest_first,
        latest_refil,
    ]
    assert repository.list_by_armadilha(armadilha.id, limit=None) == [
        first,
        middle,
        latest_first,
        latest_refil,
    ]
    assert repository.list_by_armadilha(UUID(int=0)) == []
    with pytest.raises(ValueError, match="maior que zero"):
        repository.list_by_refil(first_refil.id, limit=0)


@pytest.mark.parametrize(
    ("percentual", "status"),
    [
        (Decimal("10.00"), "inválido"),
        (Decimal("101.00"), "ok"),
    ],
)
def test_analysis_checks_are_enforced_by_postgres(
    session: Session,
    percentual: Decimal,
    status: str,
) -> None:
    """Confirma que o banco rejeita estados e percentuais fora do domínio."""
    armadilha = ArmadilhaRepository(session).create(identificador="ARM-001")
    refil = RefilRepository(session).create(
        armadilha_id=armadilha.id,
        data_instalacao=date(2026, 1, 1),
    )
    session.add(
        Analise(
            refil_id=refil.id,
            analisado_em=datetime(2026, 1, 2, tzinfo=timezone.utc),
            percentual_coberto=percentual,
            status=status,
            caminho_imagem="analises/teste.jpg",
            modelo_versao="v1.0.0+12345678",
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_analysis_repository_rejects_unknown_status_before_database(
    session: Session,
) -> None:
    """Converte a classificação antes de adicionar a análise à sessão."""
    armadilha = ArmadilhaRepository(session).create(identificador="ARM-STATUS")
    refil = RefilRepository(session).create(
        armadilha_id=armadilha.id,
        data_instalacao=date(2026, 1, 1),
    )

    with pytest.raises(ValueError):
        AnaliseRepository(session).create(
            refil_id=refil.id,
            analisado_em=datetime(2026, 1, 2, tzinfo=timezone.utc),
            percentual_coberto=Decimal("10.00"),
            status="invalido",
            caminho_imagem="analises/teste.jpg",
            modelo_versao="v1.0.0+12345678",
        )


def test_entity_metadata_matches_migrated_schema(session: Session) -> None:
    """Detecta diferenças de nomes, tipos e restrições entre ORM e banco."""
    migration_context = MigrationContext.configure(
        session.connection(),
        opts={"compare_type": True, "compare_server_default": True},
    )
    differences = compare_metadata(migration_context, Base.metadata)
    assert differences == []

    assert set(Base.metadata.tables) == {"armadilha", "refil", "analise"}
    assert {constraint.name for constraint in Armadilha.__table__.constraints} == {
        "pk_armadilha",
        "uq_armadilha_identificador",
    }
    assert {constraint.name for constraint in Refil.__table__.constraints} == {
        "pk_refil",
        "fk_refil_armadilha_id",
        "ck_refil_datas",
    }
    assert {constraint.name for constraint in Analise.__table__.constraints} == {
        "pk_analise",
        "fk_analise_refil_id",
        "ck_analise_percentual_coberto",
        "ck_analise_status",
    }
    assert "delete" not in Armadilha.refis.property.cascade
    assert "delete" not in Refil.analises.property.cascade


def test_only_one_active_refil_per_armadilha(session: Session) -> None:
    """Rejeita um segundo ciclo aberto para a mesma armadilha."""
    armadilha = ArmadilhaRepository(session).create(identificador="ARM-UNICO")
    repository = RefilRepository(session)
    repository.create(
        armadilha_id=armadilha.id,
        data_instalacao=date(2026, 1, 1),
    )

    with pytest.raises(RefilAtivoExistente) as captured:
        repository.create(
            armadilha_id=armadilha.id,
            data_instalacao=date(2026, 2, 1),
        )

    assert "constraint" not in str(captured.value).lower()
    assert "sqlalchemy" not in str(captured.value).lower()


def test_active_refils_can_coexist_for_different_armadilhas(session: Session) -> None:
    """Permite um ciclo aberto independente em cada armadilha."""
    armadilha_a = ArmadilhaRepository(session).create(identificador="ARM-A")
    armadilha_b = ArmadilhaRepository(session).create(identificador="ARM-B")
    repository = RefilRepository(session)

    refil_a = repository.create(
        armadilha_id=armadilha_a.id,
        data_instalacao=date(2026, 1, 1),
    )
    refil_b = repository.create(
        armadilha_id=armadilha_b.id,
        data_instalacao=date(2026, 1, 1),
    )

    assert repository.get_active_for_armadilha(armadilha_a.id) is refil_a
    assert repository.get_active_for_armadilha(armadilha_b.id) is refil_b


def test_closing_active_refil_allows_replacement_in_same_transaction(
    session: Session,
) -> None:
    """Permite trocar o ciclo após gravar o encerramento na mesma transação."""
    armadilha = ArmadilhaRepository(session).create(identificador="ARM-TROCA")
    repository = RefilRepository(session)
    anterior = repository.create(
        armadilha_id=armadilha.id,
        data_instalacao=date(2026, 1, 1),
    )

    assert repository.close(anterior.id, date(2026, 2, 1)) is anterior
    novo = repository.create(
        armadilha_id=armadilha.id,
        data_instalacao=date(2026, 2, 1),
    )

    assert repository.get_active_for_armadilha(armadilha.id) is novo
    assert repository.list_closed_for_armadilha(armadilha.id) == [anterior]


def test_multiple_closed_refils_are_allowed(session: Session) -> None:
    """Mantém o histórico completo de ciclos encerrados da armadilha."""
    armadilha = ArmadilhaRepository(session).create(identificador="ARM-HIST")
    repository = RefilRepository(session)

    first = repository.create(
        armadilha_id=armadilha.id,
        data_instalacao=date(2026, 1, 1),
        data_troca=date(2026, 2, 1),
    )
    second = repository.create(
        armadilha_id=armadilha.id,
        data_instalacao=date(2026, 2, 1),
        data_troca=date(2026, 3, 1),
    )

    assert repository.list_closed_for_armadilha(armadilha.id) == [first, second]


def test_close_refil_validates_current_state_and_installation_date(
    session: Session,
) -> None:
    """Impede reencerramento e datas anteriores sem alterar o ciclo ativo."""
    armadilha = ArmadilhaRepository(session).create(identificador="ARM-DATAS")
    repository = RefilRepository(session)
    closed = repository.create(
        armadilha_id=armadilha.id,
        data_instalacao=date(2026, 1, 1),
        data_troca=date(2026, 1, 31),
    )
    active = repository.create(
        armadilha_id=armadilha.id,
        data_instalacao=date(2026, 2, 1),
    )

    with pytest.raises(RefilJaEncerrado):
        repository.close(closed.id, date(2026, 2, 1))
    with pytest.raises(DataTrocaInvalida):
        repository.close(active.id, date(2026, 1, 31))

    assert closed.data_troca == date(2026, 1, 31)
    assert active.data_troca is None
    assert repository.close(active.id, date(2026, 2, 28)) is active
    assert repository.close(UUID(int=0), date(2026, 3, 1)) is None


def test_create_refil_rejects_exchange_date_before_installation(
    session: Session,
) -> None:
    """Rejeita datas incoerentes antes de adicionar o refil à sessão."""
    armadilha = ArmadilhaRepository(session).create(identificador="ARM-CREATE-DATA")
    repository = RefilRepository(session)

    with pytest.raises(DataTrocaInvalida):
        repository.create(
            armadilha_id=armadilha.id,
            data_instalacao=date(2026, 2, 1),
            data_troca=date(2026, 1, 31),
        )

    assert repository.get_active_for_armadilha(armadilha.id) is None
    assert repository.list_closed_for_armadilha(armadilha.id) == []


def test_refil_date_check_remains_enforced_by_postgres(session: Session) -> None:
    """Mantém a constraint do banco como barreira para gravações diretas."""
    armadilha = ArmadilhaRepository(session).create(identificador="ARM-CHECK-DATA")
    session.add(
        Refil(
            armadilha_id=armadilha.id,
            data_instalacao=date(2026, 2, 1),
            data_troca=date(2026, 1, 31),
        )
    )

    with pytest.raises(IntegrityError):
        session.flush()


def test_domain_exceptions_share_a_common_base() -> None:
    """Permite que chamadores capturem as falhas de domínio em conjunto."""
    assert issubclass(IdentificadorDuplicado, ErroDeDominio)
    assert issubclass(RefilAtivoExistente, ErroDeDominio)
    assert issubclass(RefilJaEncerrado, ErroDeDominio)
    assert issubclass(DataTrocaInvalida, ErroDeDominio)


def test_database_rejects_duplicate_active_refil_without_repository(
    session: Session,
) -> None:
    """Confirma que o índice também bloqueia inserções SQL diretas."""
    armadilha = ArmadilhaRepository(session).create(identificador="ARM-SQL")
    RefilRepository(session).create(
        armadilha_id=armadilha.id,
        data_instalacao=date(2026, 1, 1),
    )

    with pytest.raises(IntegrityError):
        session.execute(
            text(
                "INSERT INTO refil (armadilha_id, data_instalacao) "
                "VALUES (:armadilha_id, :data_instalacao)"
            ),
            {
                "armadilha_id": armadilha.id,
                "data_instalacao": date(2026, 2, 1),
            },
        )
