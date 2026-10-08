"""Testes do contrato e do stub local de inferência."""

import struct
import zlib
from dataclasses import FrozenInstanceError, is_dataclass
from decimal import Decimal
from io import BytesIO

import pytest
from PIL import Image

from src.config.settings import Settings
from src.entities.status import StatusAnalise
from src.inference import (
    FalhaInferencia,
    Inferidor,
    ResultadoInferencia,
    criar_inferidor,
    derivar_status,
)
from src.inference.contrato import LIMITE_PIXELS_IMAGEM
from src.inference.stub import InferidorStub


def criar_png(
    tamanho: tuple[int, int] = (20, 10),
    cor: tuple[int, int, int] = (0, 0, 0),
) -> bytes:
    """Gera uma imagem pequena em memória para os testes do stub."""
    buffer = BytesIO()
    Image.new("RGB", tamanho, cor).save(buffer, format="PNG")
    return buffer.getvalue()


def criar_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Fornece configuração fictícia sem depender de um arquivo de ambiente."""
    valores = {
        "DATABASE_URL": "postgresql://fake:fake@localhost/fake",
        "MODEL_WEIGHTS_PATH": "/caminho/ficticio/pesos.pt",
        "MODEL_VERSION": "v1.2.3",
        "UPLOADS_DIR": "/diretorio/ficticio",
        "CORS_ORIGENS": "http://localhost:5173",
        "LIMIAR_ATENCAO": "40",
        "LIMIAR_TROCAR": "70",
    }
    for nome, valor in valores.items():
        monkeypatch.setenv(nome, valor)
    return Settings()


@pytest.mark.parametrize(
    "modelo_versao",
    [
        "v1.2.0+a3f9c2e1",
        "v0.1.0-dev+00000000",
        "0.1.0-rc.1+00000000",
        "1.2.3+ABCDEF09",
    ],
)
def test_resultado_aceita_semver_com_hash_de_oito_hexadecimais(
    modelo_versao: str,
) -> None:
    resultado = ResultadoInferencia(
        percentual_coberto=Decimal("10"),
        status=StatusAnalise.OK,
        modelo_versao=modelo_versao,
        mascara=b"png",
    )

    assert resultado.modelo_versao == modelo_versao


@pytest.mark.parametrize(
    "modelo_versao",
    [
        "1.2.3",
        "1.2.3+0000000",
        "1.2.3+000000000",
        "1.2.3+0000000g",
        "1.2+00000000",
        "1.2.3-01+00000000",
    ],
)
def test_resultado_rejeita_versao_fora_de_semver_com_hash(
    modelo_versao: str,
) -> None:
    with pytest.raises(ValueError):
        ResultadoInferencia(
            percentual_coberto=Decimal("10"),
            status=StatusAnalise.OK,
            modelo_versao=modelo_versao,
            mascara=b"png",
        )


def test_stub_valida_semver_ao_construir_e_emite_versao_com_hash() -> None:
    inferidor = InferidorStub(
        modelo_versao="v0.1.0-dev",
        limiar_atencao=Decimal("40"),
        limiar_trocar=Decimal("70"),
    )

    resultado = inferidor.inferir(criar_png())

    assert resultado.modelo_versao == "v0.1.0-dev+00000000"
    with pytest.raises(ValueError):
        InferidorStub(
            modelo_versao="v0.1-dev",
            limiar_atencao=Decimal("40"),
            limiar_trocar=Decimal("70"),
        )


def test_stub_converte_erro_de_decompression_bomb_em_falha_de_inferencia(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inferidor = InferidorStub(
        modelo_versao="v0.1.0-dev",
        limiar_atencao=Decimal("40"),
        limiar_trocar=Decimal("70"),
    )

    def abrir_imagem(*args: object, **kwargs: object) -> Image.Image:
        raise Image.DecompressionBombError("mensagem técnica privada")

    monkeypatch.setattr(Image, "open", abrir_imagem)

    with pytest.raises(FalhaInferencia) as erro:
        inferidor.inferir(criar_png())

    assert str(erro.value) == "A imagem não pôde ser processada."
    assert "privada" not in str(erro.value)


@pytest.mark.parametrize(
    ("percentual", "status_esperado"),
    [
        (Decimal("39.99"), StatusAnalise.OK),
        (Decimal("40.00"), StatusAnalise.ATENCAO),
        (Decimal("70.00"), StatusAnalise.ATENCAO),
        (Decimal("70.01"), StatusAnalise.TROCAR),
    ],
)
def test_derivar_status_respeita_fronteiras(
    percentual: Decimal,
    status_esperado: StatusAnalise,
) -> None:
    assert derivar_status(percentual, Decimal("40"), Decimal("70")) is status_esperado


def test_stub_produz_resultado_imutavel_e_coerente(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inferidor = criar_inferidor(criar_settings(monkeypatch))
    resultado = inferidor.inferir(criar_png())

    assert isinstance(inferidor, Inferidor)
    assert is_dataclass(resultado)
    assert resultado.percentual_coberto == Decimal("55.00")
    assert resultado.percentual_coberto.as_tuple().exponent == -2
    assert Decimal("0") <= resultado.percentual_coberto <= Decimal("100")
    assert resultado.status is StatusAnalise.ATENCAO
    assert resultado.status == derivar_status(
        resultado.percentual_coberto,
        Decimal("40"),
        Decimal("70"),
    )
    assert resultado.modelo_versao == "v1.2.3+00000000"
    with pytest.raises(FrozenInstanceError):
        resultado.status = StatusAnalise.OK


def test_mascara_e_png_sobreposto_deterministico_e_na_resolucao_original(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inferidor = criar_inferidor(criar_settings(monkeypatch))
    imagem_original = criar_png(tamanho=(32, 20))
    primeiro = inferidor.inferir(imagem_original)
    segundo = inferidor.inferir(imagem_original)

    assert primeiro.mascara == segundo.mascara
    assert primeiro.mascara.startswith(b"\x89PNG\r\n\x1a\n")
    with Image.open(BytesIO(primeiro.mascara)) as mascara:
        assert mascara.format == "PNG"
        assert mascara.size == (32, 20)
        mascara_rgba = mascara.convert("RGBA")
        assert mascara_rgba.getpixel((0, 0)) == (102, 0, 102, 255)
        assert mascara_rgba.getpixel((0, 19)) == (0, 0, 0, 255)


@pytest.mark.parametrize(
    "imagem",
    [b"conteudo que nao e uma imagem", criar_png()[:30]],
    ids=["bytes-invalidos", "arquivo-truncado"],
)
def test_bytes_invalidos_e_truncados_geram_falha_sem_detalhes_de_pillow(
    monkeypatch: pytest.MonkeyPatch,
    imagem: bytes,
) -> None:
    inferidor = criar_inferidor(criar_settings(monkeypatch))

    with pytest.raises(FalhaInferencia) as erro:
        inferidor.inferir(imagem)

    assert str(erro.value) == "A imagem não pôde ser processada."
    assert erro.value.__cause__ is None


def test_imagem_acima_do_teto_de_pixels_falha_antes_de_decodificar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inferidor = criar_inferidor(criar_settings(monkeypatch))
    cabecalho = bytearray(criar_png(tamanho=(1, 1)))
    cabecalho[16:20] = struct.pack(">I", LIMITE_PIXELS_IMAGEM + 1)
    cabecalho[20:24] = struct.pack(">I", 1)
    crc_ihdr = zlib.crc32(cabecalho[12:29]) & 0xFFFFFFFF
    cabecalho[29:33] = struct.pack(">I", crc_ihdr)

    with pytest.raises(FalhaInferencia, match="imagem não pôde ser processada"):
        inferidor.inferir(bytes(cabecalho))


def test_resultado_arredonda_para_duas_casas_e_rejeita_percentual_invalido() -> None:
    resultado = ResultadoInferencia(
        percentual_coberto=Decimal("10.125"),
        status=StatusAnalise.OK,
        modelo_versao="1.2.3+00000000",
        mascara=b"png",
    )
    assert resultado.percentual_coberto == Decimal("10.13")
    assert resultado.percentual_coberto.as_tuple().exponent == -2

    with pytest.raises(ValueError):
        ResultadoInferencia(
            percentual_coberto=Decimal("100.01"),
            status=StatusAnalise.TROCAR,
            modelo_versao="1.2.3+00000000",
            mascara=b"png",
        )
