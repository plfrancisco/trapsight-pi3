"""Exporta um checkpoint e confere a paridade em amostras de treino."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path

import numpy as np
import onnxruntime as ort
import torch
from PIL import Image

from training.treino.modelo import carregar_checkpoint


def sha256(caminho: Path) -> str:
    """Calcula o SHA-256 de um arquivo sem carregá-lo inteiro em memória."""
    with caminho.open("rb") as arquivo:
        return hashlib.file_digest(arquivo, "sha256").hexdigest()


def main() -> None:
    """Exporta a rede e verifica logits e rótulos em imagens de treino."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("destino", type=Path)
    parser.add_argument("--versao", required=True, help="Versão SemVer sem hash")
    args = parser.parse_args()
    amostras = []
    with (args.dataset / "metadados.jsonl").open(encoding="utf-8") as arquivo:
        for linha in arquivo:
            registro = json.loads(linha)
            if registro.get("conjunto") == "treino":
                amostras.append(args.dataset / "imagens" / f"{registro['id']}.png")
                if len(amostras) == 3:
                    break
    if len(amostras) < 2:
        raise RuntimeError("O dataset deve conter ao menos duas imagens de treino.")
    modelo, checkpoint = carregar_checkpoint(args.checkpoint)
    modelo.eval()
    args.destino.parent.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(
        modelo,
        torch.zeros(1, 3, 576, 768),
        str(args.destino),
        input_names=["imagem"],
        output_names=["logits"],
        dynamo=False,
        opset_version=17,
    )
    sessao = ort.InferenceSession(str(args.destino), providers=["CPUExecutionProvider"])
    media = np.array(checkpoint["normalizacao"]["media"], dtype=np.float32).reshape(
        1, 3, 1, 1
    )
    desvio = np.array(checkpoint["normalizacao"]["desvio"], dtype=np.float32).reshape(
        1, 3, 1, 1
    )
    for caminho in amostras:
        with Image.open(caminho) as imagem:
            pixels = np.asarray(
                imagem.convert("RGB").resize((768, 576), Image.Resampling.BILINEAR),
                dtype=np.float32,
            )
        entrada = (pixels.transpose(2, 0, 1)[None] / np.float32(255) - media) / desvio
        with torch.inference_mode():
            referencia = modelo(torch.from_numpy(entrada)).numpy()
        resultado = sessao.run(None, {sessao.get_inputs()[0].name: entrada})[0]
        if not np.allclose(
            referencia, resultado, atol=1e-3, rtol=1e-4
        ) or not np.array_equal(referencia.argmax(1), resultado.argmax(1)):
            raise RuntimeError(f"Paridade falhou para {caminho.name}.")
    checkpoint_sha = sha256(args.checkpoint)
    metadados = {
        "versao": f"{args.versao}+{checkpoint_sha[:8]}",
        "onnx_sha256": sha256(args.destino),
        "checkpoint_sha256": checkpoint_sha,
        "entrada": checkpoint["entrada"],
        "normalizacao": checkpoint["normalizacao"],
        "classes": checkpoint["classes"],
        "data": date.today().isoformat(),
    }
    args.destino.with_suffix(".json").write_text(
        json.dumps(metadados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
