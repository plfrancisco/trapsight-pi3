"""Testes do carregamento e do processamento da U-Net em CPU."""

import hashlib
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from src.entities.status import StatusAnalise
from src.inference.contrato import FalhaInferencia, PlacaNaoDetectada
from src.inference.modelo import InferidorModelo


@pytest.fixture
def torch_module() -> Any:
    """Carrega PyTorch somente quando o ambiente de teste inclui inferência."""
    return pytest.importorskip("torch")


def _modelo_minimo(torch: Any, modo: str = "cobertura") -> Any:
    """Cria uma rede pequena que gera logits previsíveis por coordenada."""

    class ModeloMinimo(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.bias = torch.nn.Parameter(torch.zeros(3))

        def forward(self, entrada: Any) -> Any:
            lote, _canais, altura, largura = entrada.shape
            logits = torch.zeros(
                (lote, 3, altura, largura),
                dtype=entrada.dtype,
                device=entrada.device,
            )
            if modo == "fundo":
                logits[:, 0] = 2
            else:
                logits[:, 1] = 1
                logits[:, 2, :, : largura // 4] = 2
            return logits + self.bias.view(1, 3, 1, 1)

    return ModeloMinimo()


def _configurar_construtor(
    monkeypatch: pytest.MonkeyPatch,
    torch: Any,
    modo: str = "cobertura",
) -> None:
    """Substitui a arquitetura por uma rede pequena com o mesmo contrato."""
    smp = pytest.importorskip("segmentation_models_pytorch")
    monkeypatch.setattr(
        smp,
        "Unet",
        lambda **_parametros: _modelo_minimo(torch, modo),
    )


def _checkpoint(
    torch: Any,
    caminho: Path,
    *,
    classes: int = 3,
    arquitetura: str = "Unet",
    largura: int = 768,
    media: tuple[float, ...] = (0.485, 0.456, 0.406),
) -> Path:
    """Grava um checkpoint pequeno com o formato de metadados do treino."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "state_dict": _modelo_minimo(torch).state_dict(),
            "arquitetura": {
                "nome": arquitetura,
                "encoder": "resnet34",
                "classes": classes,
            },
            "entrada": {"largura": largura, "altura": 576},
            "normalizacao": {
                "media": list(media),
                "desvio": [0.229, 0.224, 0.225],
            },
            "classes": ["fundo", "placa_limpa", "placa_coberta"],
        },
        caminho,
    )
    return caminho


def _imagem_png(tamanho: tuple[int, int] = (64, 48)) -> bytes:
    """Cria uma imagem em memória na resolução original escolhida pelo teste."""
    buffer = BytesIO()
    Image.new("RGB", tamanho, (255, 255, 255)).save(buffer, format="PNG")
    return buffer.getvalue()


def _inferidor(caminho: Path) -> InferidorModelo:
    """Configura um inferidor com limiares reduzidos para teste."""
    return InferidorModelo(
        caminho_pesos=caminho,
        modelo_versao="v1.2.3",
        limiar_atencao=Decimal("10"),
        limiar_trocar=Decimal("20"),
    )


def test_checkpoint_produz_percentual_hash_mascara_original_e_resultado_deterministico(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    torch_module: Any,
) -> None:
    """Confere a área medida, a versão e o overlay PNG da imagem recebida."""
    _configurar_construtor(monkeypatch, torch_module)
    caminho = _checkpoint(torch_module, tmp_path / "mini.pt")
    inferidor = _inferidor(caminho)
    imagem = _imagem_png()

    primeiro = inferidor.inferir(imagem)
    segundo = inferidor.inferir(imagem)

    hash_curto = hashlib.sha256(caminho.read_bytes()).hexdigest()[:8]
    assert primeiro.percentual_coberto == Decimal("25.00")
    assert primeiro.status is StatusAnalise.TROCAR
    assert primeiro.modelo_versao == f"v1.2.3+{hash_curto}"
    assert primeiro.mascara == segundo.mascara
    with Image.open(BytesIO(primeiro.mascara)) as mascara:
        assert mascara.format == "PNG"
        assert mascara.size == (64, 48)
        assert mascara.convert("RGB").getpixel((4, 20)) == (255, 153, 255)
        assert mascara.convert("RGB").getpixel((60, 20)) == (255, 255, 255)


@pytest.mark.parametrize(
    ("nome_arquivo", "conteudo", "mensagem"),
    [
        ("ausente.pt", None, "não encontrado"),
        ("corrompido.pt", b"nao e um checkpoint", "inválido"),
    ],
)
def test_checkpoint_ausente_ou_corrompido_falha_na_inicializacao(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    torch_module: Any,
    nome_arquivo: str,
    conteudo: bytes | None,
    mensagem: str,
) -> None:
    """Recusa arquivos de pesos ausentes ou que não podem ser desserializados."""
    _configurar_construtor(monkeypatch, torch_module)
    caminho = tmp_path / nome_arquivo
    if conteudo is not None:
        caminho.write_bytes(conteudo)

    with pytest.raises(RuntimeError, match=mensagem):
        _inferidor(caminho)


@pytest.mark.parametrize(
    ("opcoes", "mensagem"),
    [
        ({"classes": 2}, "três classes"),
        ({"arquitetura": "UnetPlusPlus"}, "arquitetura deve ser Unet"),
        ({"largura": 512}, "resolução esperada"),
        ({"media": (0.5, 0.5, 0.5)}, "normalização ImageNet"),
    ],
)
def test_checkpoint_recusa_metadados_incompativeis(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    torch_module: Any,
    opcoes: dict[str, Any],
    mensagem: str,
) -> None:
    """Valida arquitetura, classes, dimensões e normalização antes do forward."""
    _configurar_construtor(monkeypatch, torch_module)
    caminho = _checkpoint(torch_module, tmp_path / "incompativel.pt", **opcoes)

    with pytest.raises(RuntimeError, match=mensagem):
        _inferidor(caminho)


def test_checkpoint_sem_area_de_placa_levanta_erro_especifico(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    torch_module: Any,
) -> None:
    """Não calcula cobertura quando a rede prevê apenas pixels de fundo."""
    _configurar_construtor(monkeypatch, torch_module, modo="fundo")
    caminho = _checkpoint(torch_module, tmp_path / "fundo.pt")

    with pytest.raises(PlacaNaoDetectada):
        _inferidor(caminho).inferir(_imagem_png())


def test_imagem_invalida_preserva_mensagem_generica(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    torch_module: Any,
) -> None:
    """Oculta detalhes do decodificador em falhas de entrada."""
    _configurar_construtor(monkeypatch, torch_module)
    inferidor = _inferidor(_checkpoint(torch_module, tmp_path / "mini.pt"))

    with pytest.raises(FalhaInferencia) as erro:
        inferidor.inferir(b"arquivo truncado ou invalido")

    assert str(erro.value) == "A imagem não pôde ser processada."
    assert erro.value.__cause__ is None


def test_fabrica_recusa_pesos_invalidos_ao_criar_aplicacao(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Confirma que o modo de modelo falha antes da aplicação subir."""
    pytest.importorskip("torch")
    pytest.importorskip("segmentation_models_pytorch")
    monkeypatch.setenv("DATABASE_URL", "postgresql://fake:fake@localhost/fake")
    monkeypatch.setenv("MODEL_WEIGHTS_PATH", str(tmp_path / "ausente.pt"))
    monkeypatch.setenv("MODEL_VERSION", "v1.2.3")
    monkeypatch.setenv("INFERENCE_MODE", "stub")
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    monkeypatch.setenv("CORS_ORIGENS", "http://localhost:5173")

    from src.main import create_app

    monkeypatch.setenv("INFERENCE_MODE", "modelo")

    with pytest.raises(RuntimeError, match="não encontrado"):
        create_app()


def test_checkpoint_com_chaves_obrigatorias_ausentes_falha(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    torch_module: Any,
) -> None:
    """Recusa metadados incompletos antes de construir a rede."""
    _configurar_construtor(monkeypatch, torch_module)
    caminho = _checkpoint(torch_module, tmp_path / "incompleto.pt")
    bruto = torch_module.load(caminho, weights_only=True, map_location="cpu")
    del bruto["normalizacao"]
    torch_module.save(bruto, caminho)

    with pytest.raises(RuntimeError, match="normalizacao"):
        _inferidor(caminho)
