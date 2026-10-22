"""Augmentation do treino (treino_spec.md, seção 5).

Aplicada somente ao conjunto de treino. A variação fotométrica é sorteada sem
olhar nenhum metadado da amostra, para não reintroduzir a correlação entre tom
da placa e cobertura que o gerador removeu. Transformações que alteram a razão
entre áreas (recortes, MixUp, CutMix) não existem aqui de propósito.
"""

from __future__ import annotations

import math

import albumentations as A
import cv2
import numpy as np
from albumentations.pytorch import ToTensorV2

MEDIA_IMAGENET = (0.485, 0.456, 0.406)
DESVIO_IMAGENET = (0.229, 0.224, 0.225)


class GanhoPorCanal(A.ImageOnlyTransform):
    """Ganho multiplicativo independente em cada canal RGB (balanço de branco)."""

    def __init__(self, ganho: tuple[float, float] = (0.75, 1.25), p: float = 0.8):
        super().__init__(p=p)
        self.ganho = ganho

    def get_params(self) -> dict[str, list[float]]:
        return {"ganhos": [self.py_random.uniform(*self.ganho) for _ in range(3)]}

    def apply(self, img: np.ndarray, ganhos: list[float], **_: object) -> np.ndarray:
        saida = img.astype(np.float32) * np.asarray(ganhos, dtype=np.float32)
        return np.clip(saida, 0, 255).astype(np.uint8)

    def get_transform_init_args_names(self) -> tuple[str, ...]:
        return ("ganho",)


class GradienteIluminacao(A.ImageOnlyTransform):
    """Gradiente linear de iluminação, como o de lâmpadas pontuais e próximas."""

    def __init__(self, profundidade_maxima: float = 0.30, p: float = 0.5):
        super().__init__(p=p)
        self.profundidade_maxima = profundidade_maxima

    def get_params(self) -> dict[str, float]:
        return {
            "angulo": self.py_random.uniform(0.0, 2.0 * math.pi),
            "profundidade": self.py_random.uniform(0.0, self.profundidade_maxima),
        }

    def apply(
        self, img: np.ndarray, angulo: float, profundidade: float, **_: object
    ) -> np.ndarray:
        altura, largura = img.shape[:2]
        ys, xs = np.mgrid[0:altura, 0:largura].astype(np.float32)
        projecao = (xs / largura - 0.5) * math.cos(angulo) + (
            ys / altura - 0.5
        ) * math.sin(angulo)
        escala = 0.5 * (abs(math.cos(angulo)) + abs(math.sin(angulo)))
        fator = 1.0 + profundidade * (projecao / max(escala, 1e-6))
        saida = img.astype(np.float32) * fator[..., None]
        return np.clip(saida, 0, 255).astype(np.uint8)

    def get_transform_init_args_names(self) -> tuple[str, ...]:
        return ("profundidade_maxima",)


class ReflexoEspecular(A.ImageOnlyTransform):
    """Manchas gaussianas que estouram para branco, como o brilho das lâmpadas."""

    def __init__(
        self,
        manchas_maximas: int = 2,
        raio: tuple[float, float] = (0.03, 0.08),
        p: float = 0.4,
    ):
        super().__init__(p=p)
        self.manchas_maximas = manchas_maximas
        self.raio = raio

    def get_params(self) -> dict[str, list[tuple[float, float, float, float]]]:
        quantidade = self.py_random.randint(1, self.manchas_maximas)
        return {
            "manchas": [
                (
                    self.py_random.uniform(0.0, 1.0),
                    self.py_random.uniform(0.0, 1.0),
                    self.py_random.uniform(*self.raio),
                    self.py_random.uniform(0.6, 1.0),
                )
                for _ in range(quantidade)
            ]
        }

    def apply(
        self,
        img: np.ndarray,
        manchas: list[tuple[float, float, float, float]],
        **_: object,
    ) -> np.ndarray:
        altura, largura = img.shape[:2]
        ys, xs = np.mgrid[0:altura, 0:largura].astype(np.float32)
        saida = img.astype(np.float32)
        for cx, cy, raio, intensidade in manchas:
            sigma = max(raio * largura, 1.0)
            distancia2 = (xs - cx * largura) ** 2 + (ys - cy * altura) ** 2
            brilho = np.exp(-distancia2 / (2.0 * sigma**2)) * intensidade
            saida = saida + (255.0 - saida) * brilho[..., None]
        return np.clip(saida, 0, 255).astype(np.uint8)

    def get_transform_init_args_names(self) -> tuple[str, ...]:
        return ("manchas_maximas", "raio")


class SombraMoldura(A.ImageOnlyTransform):
    """Escurece as bordas da imagem, como a sombra projetada pela moldura."""

    def __init__(
        self,
        largura: tuple[float, float] = (0.03, 0.08),
        escurecimento_maximo: float = 0.35,
        p: float = 0.4,
    ):
        super().__init__(p=p)
        self.largura = largura
        self.escurecimento_maximo = escurecimento_maximo

    def get_params(self) -> dict[str, list[tuple[int, float, float]]]:
        lados = [lado for lado in range(4) if self.py_random.random() < 0.5]
        if not lados:
            lados = [self.py_random.randrange(4)]
        return {
            "sombras": [
                (
                    lado,
                    self.py_random.uniform(*self.largura),
                    self.py_random.uniform(0.1, self.escurecimento_maximo),
                )
                for lado in lados
            ]
        }

    def apply(
        self, img: np.ndarray, sombras: list[tuple[int, float, float]], **_: object
    ) -> np.ndarray:
        altura, largura = img.shape[:2]
        ys, xs = np.mgrid[0:altura, 0:largura].astype(np.float32)
        distancias = (xs / largura, 1 - xs / largura, ys / altura, 1 - ys / altura)
        fator = np.ones((altura, largura), dtype=np.float32)
        for lado, espessura, escurecimento in sombras:
            proximidade = np.clip(1.0 - distancias[lado] / espessura, 0.0, 1.0)
            fator *= 1.0 - escurecimento * proximidade
        return np.clip(img.astype(np.float32) * fator[..., None], 0, 255).astype(
            np.uint8
        )

    def get_transform_init_args_names(self) -> tuple[str, ...]:
        return ("largura", "escurecimento_maximo")


def _normalizacao() -> list[A.BasicTransform]:
    return [
        A.Normalize(mean=MEDIA_IMAGENET, std=DESVIO_IMAGENET, max_pixel_value=255.0),
        ToTensorV2(),
    ]


def transformacao_avaliacao() -> A.Compose:
    """Validação e teste: só a normalização, sem nenhuma transformação."""
    return A.Compose(_normalizacao())


def transformacao_treino(semente: int | None = None) -> A.Compose:
    """Pipeline de augmentation do treino, geométrica primeiro e depois fotométrica."""
    geometricas = [
        A.HorizontalFlip(p=0.5),
        A.VerticalFlip(p=0.5),
        A.Affine(
            scale=(0.9, 1.1),
            translate_percent=(-0.05, 0.05),
            rotate=(-10, 10),
            keep_ratio=True,
            interpolation=cv2.INTER_LINEAR,
            mask_interpolation=cv2.INTER_NEAREST,
            border_mode=cv2.BORDER_CONSTANT,
            fill=0,
            fill_mask=0,
            p=0.8,
        ),
        A.Perspective(
            scale=(0.0, 0.03),
            keep_size=True,
            interpolation=cv2.INTER_LINEAR,
            mask_interpolation=cv2.INTER_NEAREST,
            fill=0,
            fill_mask=0,
            p=0.3,
        ),
    ]
    fotometricas = [
        A.HueSaturationValue(
            hue_shift_limit=12, sat_shift_limit=77, val_shift_limit=0, p=0.8
        ),
        GanhoPorCanal(ganho=(0.75, 1.25), p=0.8),
        A.RandomBrightnessContrast(brightness_limit=0.25, contrast_limit=0.25, p=0.8),
        GradienteIluminacao(profundidade_maxima=0.30, p=0.5),
        ReflexoEspecular(manchas_maximas=2, raio=(0.03, 0.08), p=0.4),
        SombraMoldura(largura=(0.03, 0.08), escurecimento_maximo=0.35, p=0.4),
        A.GaussianBlur(blur_limit=(3, 7), sigma_limit=(0.1, 1.5), p=0.3),
        A.GaussNoise(std_range=(0.0, 0.03), p=0.4),
        A.ImageCompression(quality_range=(60, 100), p=0.3),
    ]
    return A.Compose([*geometricas, *fotometricas, *_normalizacao()], seed=semente)
