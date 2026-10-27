"""Relaciona regiões reduzidas a recortes nativos e evidências humanas COCO.

Caixa ausente não é evidência negativa. A ferramenta registra propostas e
recortes, sem decidir classes. Processa somente um original confiável por vez.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from training.dataset_sintetico import NOMES_BASES_REAIS
from training.teste_real_ums import _abrir_reduzida, _carregar_cartoes, _preparar_saida


@dataclass(frozen=True)
class Transformacao:
    """Rotação anti-horária, redução e letterbox do produtor das imagens."""

    largura: int
    altura: int
    largura_conteudo: int
    altura_conteudo: int
    offset_x: int
    offset_y: int

    def direto(self, x: float, y: float) -> tuple[float, float]:
        return (
            self.offset_x + y * self.largura_conteudo / self.altura,
            self.offset_y + (self.largura - x) * self.altura_conteudo / self.largura,
        )

    def inverso(self, x: float, y: float) -> tuple[float, float]:
        return (
            self.largura - (y - self.offset_y) * self.largura / self.altura_conteudo,
            (x - self.offset_x) * self.altura / self.largura_conteudo,
        )

    def caixa(self, bbox: list[float]) -> list[float]:
        x, y, w, h = bbox
        x0, y0 = self.direto(x + w, y)
        x1, y1 = self.direto(x, y + h)
        return [x0, y0, x1, y1]


def evidencias(
    caixa: list[int], anotacoes: list[dict], transformacao: Transformacao
) -> list[dict]:
    """Propõe caixas humanas que contêm o centro da candidata ou a interceptam."""
    x, y, w, h = caixa
    xc, yc = x + w / 2, y + h / 2
    resultado = []
    for a in anotacoes:
        x0, y0, x1, y1 = transformacao.caixa(a["bbox"])
        intersecao = max(0, min(x + w, x1) - max(x, x0)) * max(
            0, min(y + h, y1) - max(y, y0)
        )
        centro = x0 <= xc <= x1 and y0 <= yc <= y1
        if centro or intersecao / max(1, w * h) >= 0.5:
            resultado.append(
                {
                    "anotacao_id": a["id"],
                    "taxon": a["taxon"],
                    "bbox_original_xywh": a["bbox"],
                    "bbox_reduzida_xyxy": [x0, y0, x1, y1],
                    "centro_na_caixa": centro,
                    "tipo": "proposta_baseada_em_anotacao_humana",
                }
            )
    return resultado


def recorte_original(
    original: Image.Image,
    transformacao: Transformacao,
    centro: tuple[float, float],
    lado: int = 256,
) -> tuple[Image.Image, list[int]]:
    """Recorta na escala nativa e só então gira a pequena janela para conferência."""
    x, y = transformacao.inverso(*centro)
    x0 = max(0, min(original.width - lado, round(x - lado / 2)))
    y0 = max(0, min(original.height - lado, round(y - lado / 2)))
    box = [x0, y0, min(original.width, x0 + lado), min(original.height, y0 + lado)]
    return original.crop(tuple(box)).transpose(Image.Transpose.ROTATE_90), box


def executar(
    originais: Path,
    reduzidas: Path,
    anotacoes: Path,
    saida: Path,
    somente_pendentes: bool = False,
) -> dict:
    """Valida pixels e geometria antes de produzir os painéis e as evidências."""
    if saida.exists() and any(saida.iterdir()):
        raise FileExistsError("A pasta de revisão precisa ser nova.")
    saida.mkdir(parents=True, exist_ok=True)
    cartoes = {c.nome: c for c in _carregar_cartoes(originais)}
    relatorio = []
    for nome in NOMES_BASES_REAIS:
        identificador = Path(nome).stem
        cartao = cartoes[identificador]
        if not cartao.caminho.resolve().is_relative_to(originais.resolve()):
            raise ValueError("O original precisa estar na raiz local confiável.")
        coco_path = cartao.caminho.parent / "instances_default.json"
        coco = json.loads(coco_path.read_text("utf-8"))
        categorias = {c["id"]: c["name"] for c in coco["categories"]}
        caixas = [
            {**a, "taxon": categorias[a["category_id"]]} for a in cartao.anotacoes
        ]
        arquivo = anotacoes / identificador / "regioes.json"
        dados = json.loads(arquivo.read_text("utf-8"))
        # A detecção da placa delimita a máscara; _preparar_saida não recorta a foto.
        limite_anterior = Image.MAX_IMAGE_PIXELS
        try:
            Image.MAX_IMAGE_PIXELS = None
            pequena = _abrir_reduzida(cartao.caminho, 0.25)
            reconstruida, _, _ = _preparar_saida(
                pequena, np.zeros((pequena.height, pequena.width), np.uint8)
            )
            referencia = Image.open(reduzidas / "imagens" / nome).convert("RGB")
            if not np.array_equal(np.array(reconstruida), np.array(referencia)):
                raise ValueError(f"A reconstrução não reproduz os pixels de {nome}.")
            fator = min(768 / pequena.width, 576 / pequena.height)
            nw, nh = round(pequena.width * fator), round(pequena.height * fator)
            transformacao = Transformacao(
                cartao.largura, cartao.altura, nw, nh, (768 - nw) // 2, (576 - nh) // 2
            )
            pequena.close()
            reconstruida.close()
            with Image.open(cartao.caminho) as original:
                if original.size != (cartao.largura, cartao.altura):
                    raise ValueError("Dimensões COCO e original divergem.")
                original.load()
                # Três caixas COCO de tamanhos diferentes mostram o alinhamento nas duas escalas.
                validacao = Image.new("RGB", (1024, 606), "white")
                overview = referencia.copy()
                desenho = ImageDraw.Draw(overview)
                selecionadas = sorted(caixas, key=lambda a: a["bbox"][2] * a["bbox"][3])
                escolhidas = [
                    selecionadas[0],
                    selecionadas[len(selecionadas) // 2],
                    selecionadas[-1],
                ]
                for j, a in enumerate(escolhidas):
                    box = transformacao.caixa(a["bbox"])
                    desenho.rectangle(box, outline="red", width=2)
                    desenho.text((box[0], box[1] - 10), str(a["id"]), fill="red")
                    x, y, w, h = a["bbox"]
                    margem = 30
                    cropbox = [
                        max(0, int(x - margem)),
                        max(0, int(y - margem)),
                        min(original.width, int(x + w + margem)),
                        min(original.height, int(y + h + margem)),
                    ]
                    detalhe = original.crop(tuple(cropbox))
                    d = ImageDraw.Draw(detalhe)
                    d.rectangle(
                        [
                            x - cropbox[0],
                            y - cropbox[1],
                            x + w - cropbox[0],
                            y + h - cropbox[1],
                        ],
                        outline="red",
                        width=3,
                    )
                    detalhe = detalhe.transpose(Image.Transpose.ROTATE_90)
                    detalhe.thumbnail((250, 168))
                    validacao.paste(detalhe, (770, 30 + j * 190))
                    ImageDraw.Draw(validacao).text(
                        (770, 200 + j * 190), f"{a['id']} {a['taxon']}", fill="black"
                    )
                validacao.paste(overview, (0, 30))
                ImageDraw.Draw(validacao).text(
                    (5, 5),
                    "Pixels reconstruidos identicos; caixas humanas nas duas escalas",
                    fill="black",
                )
                validacao.save(saida / f"mapeamento_{nome}")
                sem_caixa_sem_decisao = []
                com_caixa = 0
                exibidas = [
                    r
                    for r in dados["regioes"]
                    if not somente_pendentes or r["decisao"] == "ambigua"
                ]
                for inicio in range(0, len(exibidas), 20):
                    pagina = Image.new("RGB", (960, 1000), "white")
                    draw = ImageDraw.Draw(pagina)
                    for j, r in enumerate(exibidas[inicio : inicio + 20]):
                        x, y, w, h = r["caixa"]
                        evid = evidencias(r["caixa"], caixas, transformacao)
                        r["evidencia"] = {
                            "coco": evid,
                            "coco_sha256": hashlib.sha256(
                                coco_path.read_bytes()
                            ).hexdigest(),
                        }
                        alto, box = recorte_original(
                            original, transformacao, (x + w / 2, y + h / 2)
                        )
                        r["evidencia"]["recorte_original_xyxy"] = box
                        r["evidencia"]["tamanho_candidata_original_px"] = [
                            w * cartao.altura / nw,
                            h * cartao.largura / nh,
                        ]
                        xx, yy = (j % 4) * 240, (j // 4) * 200
                        baixo = referencia.crop(
                            (
                                max(0, x - 7),
                                max(0, y - 7),
                                min(768, x + w + 7),
                                min(576, y + h + 7),
                            )
                        )
                        baixo.thumbnail((64, 160))
                        alto.thumbnail((168, 168))
                        pagina.paste(baixo, (xx, yy + 22))
                        pagina.paste(alto, (xx + 68, yy + 22))
                        draw.text(
                            (xx, yy + 2), f"ID {r['id']} {r['decisao']}", fill="black"
                        )
                        taxons = (
                            ",".join(sorted({e["taxon"] for e in evid}))
                            or "SEM CAIXA (revisar)"
                        )
                        draw.text(
                            (xx, yy + 185),
                            taxons[:36],
                            fill="red" if not evid else "blue",
                        )
                        if evid:
                            com_caixa += 1
                        elif r["decisao"] == "ambigua":
                            sem_caixa_sem_decisao.append(
                                {
                                    "id": r["id"],
                                    "tamanho_original_px": r["evidencia"][
                                        "tamanho_candidata_original_px"
                                    ],
                                }
                            )
                    pagina.save(
                        saida / f"{identificador}_pagina_{inicio // 20 + 1:02}.png"
                    )
        finally:
            Image.MAX_IMAGE_PIXELS = limite_anterior
        arquivo.write_text(
            json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        registro = {
            "placa": identificador,
            "regioes": len(dados["regioes"]),
            "regioes_exibidas": len(exibidas),
            "com_caixa_coco": com_caixa,
            "sem_caixa": len(exibidas) - com_caixa,
            "sem_caixa_sem_decisao_visual": sem_caixa_sem_decisao,
            "reconstrucao_pixel_exata": True,
            "transformacao": transformacao.__dict__,
        }
        relatorio.append(registro)
        print(
            identificador,
            "COCO",
            com_caixa,
            "sem caixa/decisao",
            len(sem_caixa_sem_decisao),
            flush=True,
        )
    resultado = {"placas": relatorio, "ausencia_coco_nao_prova_sujeira": True}
    (saida / "relatorio.json").write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return resultado


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--originais", type=Path, required=True)
    p.add_argument("--reduzidas", type=Path, required=True)
    p.add_argument(
        "--anotacoes", type=Path, default=Path(__file__).with_name("anotacoes_ums")
    )
    p.add_argument("--saida", type=Path, required=True)
    p.add_argument("--somente-pendentes", action="store_true")
    a = p.parse_args()
    executar(a.originais, a.reduzidas, a.anotacoes, a.saida, a.somente_pendentes)
