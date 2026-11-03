"""Testes do contrato e da integridade do modelo ONNX empacotado."""

import json
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest

from src.inference.contrato import ResultadoInferencia
from src.inference.onnx import InferidorOnnx

MODELO = Path(__file__).resolve().parents[2] / "models" / "modelo.onnx"
DATASET = (
    Path(__file__).resolve().parents[3] / "dataset/recomposicao-real-v5-3000-20261027"
)
CHECKPOINT = Path("E:/TrapSight-dados/execucoes/20261031-034356-e1-pretreino/melhor.pt")


@pytest.fixture(scope="module")
def inferidor():
    """Carrega o modelo real uma vez para os testes de inferência."""
    return InferidorOnnx(MODELO, "v0.1.0-e1", Decimal(10), Decimal(20))


def test_modelo_ausente(tmp_path):
    with pytest.raises(RuntimeError, match="ausentes ou ilegíveis"):
        InferidorOnnx(tmp_path / "ausente.onnx", "v0.1.0-e1", Decimal(10), Decimal(20))


def test_hash_alterado(tmp_path):
    modelo = tmp_path / "modelo.onnx"
    modelo.write_bytes(b"outro modelo")
    modelo.with_suffix(".json").write_text(json.dumps({"onnx_sha256": "0" * 64}))
    with pytest.raises(RuntimeError, match="SHA-256"):
        InferidorOnnx(modelo, "v0.1.0-e1", Decimal(10), Decimal(20))


def test_forma_invalida(monkeypatch):
    import onnxruntime as ort

    class Tensor:
        shape = [1, 3, 1, 1]
        type = "tensor(float)"

    class Sessao:
        def __init__(self, *args, **kwargs):
            pass

        def get_inputs(self):
            return [Tensor()]

        def get_outputs(self):
            return [Tensor()]

    monkeypatch.setattr(ort, "InferenceSession", Sessao)
    with pytest.raises(RuntimeError, match="Dimensões"):
        InferidorOnnx(MODELO, "v0.1.0-e1", Decimal(10), Decimal(20))


def test_saida_nao_finita_impede_inicializacao(monkeypatch):
    import onnxruntime as ort

    class Tensor:
        shape = [1, 3, 576, 768]
        type = "tensor(float)"
        name = "imagem"

    class Sessao:
        def __init__(self, *args, **kwargs):
            pass

        def get_inputs(self):
            return [Tensor()]

        def get_outputs(self):
            return [Tensor()]

        def run(self, *args):
            return [np.full((1, 3, 576, 768), np.nan, dtype=np.float32)]

    monkeypatch.setattr(ort, "InferenceSession", Sessao)
    with pytest.raises(RuntimeError, match="não finitos"):
        InferidorOnnx(MODELO, "v0.1.0-e1", Decimal(10), Decimal(20))


@pytest.mark.parametrize(
    "amostra,baixa", [("amostra_000021", True), ("amostra_000012", False)]
)
def test_contrato_e_cobertura(inferidor, amostra, baixa):
    caminho = DATASET / "imagens" / f"{amostra}.png"
    if not caminho.is_file():
        pytest.skip("Dataset de treino não está disponível neste ambiente.")
    resultado = inferidor.inferir(caminho.read_bytes())
    assert isinstance(resultado, ResultadoInferencia)
    assert resultado.modelo_versao == "v0.1.0-e1+a982b9a5"
    assert resultado.mascara.startswith(b"\x89PNG\r\n\x1a\n")
    assert (
        resultado.percentual_coberto < 10
        if baixa
        else resultado.percentual_coberto > 20
    )


@pytest.mark.parametrize("amostra", ["amostra_000021", "amostra_000012"])
def test_paridade_torch(inferidor, amostra):
    torch = pytest.importorskip("torch")
    pytest.importorskip("segmentation_models_pytorch")
    if (
        not CHECKPOINT.is_file()
        or not (DATASET / "imagens" / f"{amostra}.png").is_file()
    ):
        pytest.skip("Checkpoint ou imagens de treino não estão disponíveis.")
    from src.inference.modelo import InferidorModelo
    from training.treino.modelo import carregar_checkpoint

    torch.set_num_threads(1)
    modelo, _ = carregar_checkpoint(CHECKPOINT)
    modelo.eval()
    imagem = InferidorModelo._decodificar_imagem(
        (DATASET / "imagens" / f"{amostra}.png").read_bytes()
    )
    from PIL import Image

    pixels = np.asarray(
        imagem.resize((768, 576), Image.Resampling.BILINEAR), dtype=np.float32
    )
    media = np.array((0.485, 0.456, 0.406), dtype=np.float32).reshape(1, 3, 1, 1)
    desvio = np.array((0.229, 0.224, 0.225), dtype=np.float32).reshape(1, 3, 1, 1)
    entrada = (pixels.transpose(2, 0, 1)[None] / np.float32(255) - media) / desvio
    with torch.inference_mode():
        referencia = modelo(torch.from_numpy(entrada)).numpy()
    saida = inferidor._executar(entrada)
    np.testing.assert_allclose(saida, referencia, atol=1e-3, rtol=1e-4)
    assert np.array_equal(saida.argmax(1), referencia.argmax(1))
