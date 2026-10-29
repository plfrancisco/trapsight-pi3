"""Gera imagens rotuladas de refis adesivos a partir de sprites catalogados.

O módulo cria cenas, une as silhuetas na máscara de três classes e registra a
cobertura medida no resultado final. Sprites precisam ser PNGs com canal alfa
e licença documentada no manifesto local.
"""

from __future__ import annotations

import bisect
import hashlib
import io
import json
import math
import os
import platform
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

import PIL
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter

from training.treino.configuracao import derivar_status

CategoriaSprite = Literal["pequeno", "medio", "grande"]
FaixaCobertura = Literal["ok", "atencao", "trocar"]

VALORES_CLASSES = {"fundo": 0, "placa_limpa": 1, "placa_coberta": 2}
FAIXAS_COBERTURA: tuple[tuple[FaixaCobertura, float, float], ...] = (
    ("ok", 0.0, 10.0),
    ("atencao", 10.0, 20.0),
    ("trocar", 20.0, 35.0),
)
LARGURA_MODELO = 768
ALTURA_MODELO = 576
RESOLUCAO_PADRAO = (LARGURA_MODELO, ALTURA_MODELO)
TOLERANCIA_COBERTURA_PP = 0.5
LIMITE_SPRITES_POR_AMOSTRA = 3000
TENTATIVAS_POR_SPRITE = 10
DIMENSOES_REFIL_MM = (450.0, 220.0)
PX_POR_MM_PADRAO = 1.6
K_ESCALA_MINIMO = 1.3
K_ESCALA_MAXIMO = 3.0
VARIACAO_ESCALA_MINIMA = 0.85
VARIACAO_ESCALA_MAXIMA = 1.2
GRADE_DENSIDADE_PADRAO = (24, 12)
CATEGORIAS = ("pequeno", "medio", "grande")
GRUPOS_INSETOS = (
    "mosca",
    "mosquito",
    "formiga",
    "barata",
    "mariposa",
    "besouro",
    "vespa",
    "psocoptero",
    "percevejo",
    "cupim",
    "outro",
)
PESOS_GRUPO_PADRAO = {
    "mosca": 0.20,
    "mosquito": 0.20,
    "mariposa": 0.20,
    "vespa": 0.10,
    "formiga": 0.06,
    "barata": 0.06,
    "besouro": 0.06,
    "psocoptero": 0.03,
    "percevejo": 0.03,
    "cupim": 0.03,
    "outro": 0.03,
}
FRACOES_AREA_SPRITES = {
    "pequeno": (0.0002, 0.0025),
    "medio": (0.0025, 0.012),
    "grande": (0.012, 0.04),
}
LIMITE_ALTURA_SPRITES = {"pequeno": 0.06, "medio": 0.12, "grande": 0.22}
FREQUENCIAS_DISTRATORES = (
    ("poeira", 0.88),
    ("teia", 0.14),
    ("pelos", 0.18),
    ("respingos", 0.28),
)
FAIXAS_COBERTURA_RECOMPOSICAO: tuple[tuple[FaixaCobertura, float, float], ...] = (
    ("ok", 0.0, 10.0),
    ("atencao", 10.0, 20.0),
    ("trocar", 20.0, 55.0),
)
VIES_TOLERANCIA_ALVO_PP = 1.0
FAIXAS_ALVO_RECOMPOSICAO: tuple[tuple[FaixaCobertura, float, float], ...] = (
    ("ok", 1.0, 10.9),
    ("atencao", 11.0, 20.9),
    ("trocar", 21.0, 55.0),
)
NOMES_BASES_REAIS = (
    "senai_tebrau_sb__resized_w_uv_tebrau_160824_c172.png",
    "senai_tebrau_sb__resized_w_uv_tebrau_160824_b171.png",
    "senai_tebrau_sb__resized_w_uv_tebrau_160824_a167.png",
    "luzi_sb__resized_w_uv_luzi_150824_b310.png",
    "senai_tebrau_sb__resized_w_uv_tebrau_160824_a164.png",
    "pontian_sb_b102-c124__resized_w_uv_pontian_170824_b117.png",
)
AREA_MINIMA_RECORTE_REAL = 25
PROPORCAO_MAXIMA_RECORTE_REAL = 4.0
EROSAO_PLACA_PX = 26
LIMIAR_PIXEL_ESCURO = 110
AREA_COMPONENTE_AGLOMERADO = 500
LIMITE_AGLOMERACAO_BASE_BAIXA_COBERTURA = 0.05
LADO_MAXIMO_RECORTE_DISPERSO = 14
EFICIENCIA_AREA_AGLOMERADA = 0.25
EFICIENCIA_AREA_DISPERSA = 0.9
FRACAO_RAIO_FOCO_LARGURA = 0.14
FRACAO_RAIO_FOCO_ALTURA = 0.18
FRACAO_MARGEM_DISPERSAO = 0.5
DIVISOR_ESPACAMENTO_DISPERSO = 6
NUMERO_MINIMO_FOCOS = 4
NUMERO_MAXIMO_FOCOS = 7
AMOSTRAS_DESCRITORES_VISUAIS = 60
TOLERANCIA_RECOMPOSICAO_PP = 1.0
COMPONENTES_ESCUROS_REFERENCIA = 5144


@dataclass(frozen=True)
class SpriteCatalogado:
    """Imagem recortada e procedência registrada no catálogo.

    Attributes:
        imagem: Sprite RGBA recortado no contorno não transparente.
        categoria: Grupo de tamanho usado para variar a escala de composição.
        grupo: Grupo taxonômico usado para ponderar a seleção de sprites.
        arquivo: Caminho relativo ao banco de sprites.
        autor: Autor da foto de origem.
        fonte: URL ou identificador público do conjunto de origem.
        licenca: Identificador da licença de uso do sprite.
        especie: Espécie ou tipo do inseto, quando conhecido.
        fragmentado: Indica se o sprite representa um fragmento de inseto.
        tamanho_mm: Comprimento máximo estimado do inseto em milímetros.
        px_por_mm: Resolução física usada para extrair o sprite, se conhecida.
        classe_origem: Classe taxonômica registrada pela fonte.
        origem_escala: Indica se o tamanho físico é medido ou estimado.
    """

    imagem: Image.Image
    categoria: CategoriaSprite
    grupo: str
    arquivo: str
    autor: str
    fonte: str
    licenca: str
    especie: str | None
    fragmentado: bool
    tamanho_mm: float | None = None
    px_por_mm: float | None = None
    classe_origem: str | None = None
    origem_escala: str = "desconhecida"


@dataclass(frozen=True)
class ConfiguracaoDataset:
    """Parâmetros reprodutíveis para uma execução do gerador.

    Attributes:
        diretorio_saida: Diretório novo ou vazio que receberá as imagens.
        semente: Semente global da execução.
        idade_maxima_dias: Limite superior exclusivo da idade simulada.
        quantidade: Número de amostras, estratificado nas três faixas.
        resolucao: Largura e altura de saída em pixels.
        limite_sprites: Máximo de tentativas de composição em uma amostra.
        px_por_mm: Escala de referência da placa na resolução de saída.
        k_escala_min: Limite inferior da escala visual do inseto.
        k_escala_max: Limite superior da escala visual do inseto.
        grade_densidade: Quantidade de células usadas para amostrar posições.
        diretorio_placas_reais: Diretório com imagens e máscaras reais.
        diretorio_recortes_reais: Biblioteca COCO/SAM versionada por placa.
        proporcao_bases_reais: Fração das amostras com base real.
        intensidade_aglomeracao: Fração da área nova concentrada em grupos.
        limite_reuso_recorte: Máximo de ocorrências por recorte em uma amostra.
        proporcao_placas_avaliacao: Fração das placas reservada à avaliação.
    """

    diretorio_saida: Path
    semente: int
    idade_maxima_dias: float
    quantidade: int = 3000
    resolucao: tuple[int, int] = RESOLUCAO_PADRAO
    limite_sprites: int = LIMITE_SPRITES_POR_AMOSTRA
    pesos_grupo: dict[str, float] | None = None
    px_por_mm: float = PX_POR_MM_PADRAO
    k_escala_min: float = K_ESCALA_MINIMO
    k_escala_max: float = K_ESCALA_MAXIMO
    variacao_escala_minima: float = VARIACAO_ESCALA_MINIMA
    variacao_escala_maxima: float = VARIACAO_ESCALA_MAXIMA
    grade_densidade: tuple[int, int] = GRADE_DENSIDADE_PADRAO
    diretorio_placas_reais: Path | None = None
    diretorio_recortes_reais: Path | None = None
    proporcao_bases_reais: float = 0.5
    intensidade_aglomeracao: float = 0.0
    limite_reuso_recorte: int = 2
    proporcao_placas_avaliacao: float = 0.2
    diretorio_mascaras_bases: Path | None = None
    fator_escala_recorte: float = 1.0

    def __post_init__(self) -> None:
        if self.quantidade < 1:
            raise ValueError("A quantidade precisa ser maior que zero.")
        if not math.isfinite(self.idade_maxima_dias) or self.idade_maxima_dias <= 0:
            raise ValueError("A idade máxima precisa ser um número positivo.")
        if self.limite_sprites < 1:
            raise ValueError("O limite de sprites precisa ser maior que zero.")
        if not math.isfinite(self.px_por_mm) or self.px_por_mm <= 0:
            raise ValueError(
                "A escala da placa em pixels por milímetro precisa ser positiva."
            )
        if (
            not math.isfinite(self.k_escala_min)
            or not math.isfinite(self.k_escala_max)
            or self.k_escala_min <= 0
            or self.k_escala_max < self.k_escala_min
        ):
            raise ValueError("A faixa de k precisa ser positiva e crescente.")
        if (
            not 0 < self.variacao_escala_minima <= self.variacao_escala_maxima
            or self.variacao_escala_maxima > 3
        ):
            raise ValueError("A variação de escala precisa ser positiva e limitada.")
        if min(self.grade_densidade) < 2:
            raise ValueError(
                "A grade de densidade precisa ter ao menos duas células por eixo."
            )
        if (
            isinstance(self.proporcao_bases_reais, bool)
            or not math.isfinite(self.proporcao_bases_reais)
            or not 0 <= self.proporcao_bases_reais <= 1
        ):
            raise ValueError(
                "A proporção de bases reais precisa ficar entre zero e um."
            )
        if (
            isinstance(self.intensidade_aglomeracao, bool)
            or not math.isfinite(self.intensidade_aglomeracao)
            or not 0 <= self.intensidade_aglomeracao <= 1
        ):
            raise ValueError(
                "A intensidade de aglomeração precisa ficar entre zero e um."
            )
        if self.limite_reuso_recorte < 1:
            raise ValueError("O limite de reuso de recorte precisa ser positivo.")
        if (
            not math.isfinite(self.fator_escala_recorte)
            or not 0.3 <= self.fator_escala_recorte <= 2.0
        ):
            raise ValueError("O fator de escala de recorte deve ficar entre 0,3 e 2,0.")
        if (
            isinstance(self.proporcao_placas_avaliacao, bool)
            or not math.isfinite(self.proporcao_placas_avaliacao)
            or not 0 < self.proporcao_placas_avaliacao < 1
        ):
            raise ValueError(
                "A fração de placas de avaliação precisa ficar entre zero e um."
            )
        pesos = (
            dict(PESOS_GRUPO_PADRAO)
            if self.pesos_grupo is None
            else dict(self.pesos_grupo)
        )
        if not pesos or set(pesos) - set(GRUPOS_INSETOS):
            raise ValueError("Os pesos precisam usar apenas grupos catalogados.")
        if (
            any(
                isinstance(peso, bool)
                or not isinstance(peso, (int, float))
                or not math.isfinite(peso)
                or peso < 0
                for peso in pesos.values()
            )
            or sum(pesos.values()) <= 0
        ):
            raise ValueError(
                "Os pesos precisam ser finitos, não negativos e não nulos."
            )
        object.__setattr__(self, "pesos_grupo", pesos)
        largura, altura = self.resolucao
        if largura < 100 or altura < 100:
            raise ValueError(
                "Cada dimensão da resolução precisa ter ao menos 100 pixels."
            )


@dataclass(frozen=True)
class AmostraSintetica:
    """Imagem e máscara geradas com seus metadados visuais.

    Attributes:
        imagem: Cena RGB pronta para uso no treinamento.
        mascara: Rótulos em escala de cinza: fundo 0, placa limpa 1, coberta 2.
        percentual_cobertura_real: Razão de pixels cobertos sobre a placa.
        n_sprites: Número de silhuetas compostas na placa.
        distratores_presentes: Tipos de distrator desenhados na imagem.
        dominante_cor: Descrição da dominante aplicada à cena.
        dominante_rgb: Cor RGB aplicada à superfície adesiva antes da luz.
        alvo_atingido: Indica se a máscara ficou a até meio ponto do alvo.
        px_por_mm: Escala física observada na placa composta.
        k_escala: Fator de ampliação visual amostrado para a imagem.
    """

    imagem: Image.Image
    mascara: Image.Image
    percentual_cobertura_real: float
    n_sprites: int
    distratores_presentes: list[str]
    dominante_cor: str
    dominante_rgb: tuple[int, int, int]
    alvo_atingido: bool
    px_por_mm: float
    k_escala: float


@dataclass(frozen=True)
class GeometriaPlaca:
    """Dimensões fixas da placa adesiva dentro de uma cena."""

    resolucao: tuple[int, int]
    caixa: tuple[int, int, int, int]
    margem_moldura: int
    px_por_mm: float


@dataclass(frozen=True)
class RecorteInsetoReal:
    """Componente com pixels originais e placa de origem registrada."""

    identificador: str
    placa_origem: str
    imagem: Image.Image
    area_px: int
    anotacao_coco_id: str | None = None
    taxon: str | None = None
    sha256_conteudo: str | None = None


@dataclass(frozen=True)
class BasePlacaReal:
    """Imagem real e máscara de classes que podem servir como base."""

    identificador: str
    imagem: Image.Image
    mascara: Image.Image
    percentual_herdado: float


def create_plate_geometry(
    resolucao: tuple[int, int],
    rng: random.Random,
    px_por_mm: float = PX_POR_MM_PADRAO,
) -> GeometriaPlaca:
    """Sorteia a posição e as dimensões de uma placa para reutilização."""
    largura, altura = resolucao
    if largura < 100 or altura < 100:
        raise ValueError("Cada dimensão da resolução precisa ter ao menos 100 pixels.")
    caixa, margem = _calcular_caixa_placa(largura, altura, rng, px_por_mm)
    px_por_mm_real = (caixa[2] - caixa[0]) / DIMENSOES_REFIL_MM[0]
    return GeometriaPlaca(resolucao, caixa, margem, px_por_mm_real)


def load_sprite_catalog(diretorio_sprites: Path) -> tuple[SpriteCatalogado, ...]:
    """Carrega e valida o manifesto e os sprites PNG associados.

    O manifesto `manifest.json` deve conter uma lista `sprites`, cada item com
    `arquivo`, `categoria`, `grupo`, `autor`, `fonte` e `licenca`; `especie`
    e `fragmentado` são opcionais.

    Args:
        diretorio_sprites: Diretório local do banco de sprites.

    Returns:
        Sprites RGBA recortados, ordenados como aparecem no manifesto.

    Raises:
        FileNotFoundError: Se o manifesto ou um arquivo de sprite não existir.
        ValueError: Se um registro, caminho, licença ou PNG for inválido.
    """
    raiz = diretorio_sprites.resolve()
    caminho_manifesto = raiz / "manifest.json"
    try:
        manifesto = json.loads(caminho_manifesto.read_text(encoding="utf-8"))
    except json.JSONDecodeError as erro:
        raise ValueError("O manifesto de sprites precisa ser JSON válido.") from erro

    if not isinstance(manifesto, dict) or not isinstance(
        manifesto.get("sprites"), list
    ):
        raise ValueError("O manifesto precisa conter uma lista chamada 'sprites'.")

    sprites: list[SpriteCatalogado] = []
    categorias_presentes: set[str] = set()
    arquivos_presentes: set[str] = set()
    for indice, registro in enumerate(manifesto["sprites"]):
        if not isinstance(registro, dict):
            raise ValueError(f"O registro de sprite {indice} precisa ser um objeto.")

        arquivo = _texto_obrigatorio(registro, "arquivo", indice)
        categoria = _texto_obrigatorio(registro, "categoria", indice)
        grupo = _texto_obrigatorio(registro, "grupo", indice)
        autor = _texto_obrigatorio(registro, "autor", indice)
        fonte = _texto_obrigatorio(registro, "fonte", indice)
        licenca = _texto_obrigatorio(registro, "licenca", indice)
        if categoria not in CATEGORIAS:
            raise ValueError(
                f"A categoria do sprite {indice} precisa ser pequeno, medio ou grande."
            )
        if grupo not in GRUPOS_INSETOS:
            raise ValueError(f"O grupo do sprite {indice} não é reconhecido.")
        if arquivo in arquivos_presentes:
            raise ValueError(f"O arquivo de sprite aparece mais de uma vez: {arquivo}.")
        arquivos_presentes.add(arquivo)

        caminho = (raiz / arquivo).resolve()
        if not caminho.is_relative_to(raiz):
            raise ValueError(f"O caminho do sprite escapa do banco: {arquivo}.")
        if caminho.suffix.lower() != ".png":
            raise ValueError(f"O sprite precisa estar em PNG: {arquivo}.")

        with Image.open(caminho) as imagem_aberta:
            if imagem_aberta.width * imagem_aberta.height > 40_000_000:
                raise ValueError(f"O sprite excede o limite de dimensões: {arquivo}.")
            if "A" not in imagem_aberta.getbands():
                raise ValueError(f"O sprite PNG precisa ter canal alfa: {arquivo}.")
            imagem = imagem_aberta.convert("RGBA")
        caixa = imagem.getchannel("A").getbbox()
        if caixa is None:
            raise ValueError(f"O sprite não contém pixels opacos: {arquivo}.")
        imagem = imagem.crop(caixa)

        especie = registro.get("especie")
        if especie is not None and not isinstance(especie, str):
            raise ValueError(f"A espécie do sprite {indice} precisa ser texto.")
        fragmentado = registro.get("fragmentado", False)
        if not isinstance(fragmentado, bool):
            raise ValueError(f"'fragmentado' do sprite {indice} precisa ser booleano.")
        tamanho_mm = _numero_positivo_opcional(registro, "tamanho_mm", indice)
        px_por_mm = _numero_positivo_opcional(registro, "px_por_mm", indice)
        classe_origem = registro.get("classe_origem")
        if classe_origem is not None and not isinstance(classe_origem, str):
            raise ValueError(f"'classe_origem' do sprite {indice} precisa ser texto.")
        origem_escala = registro.get("origem_escala", "desconhecida")
        if not isinstance(origem_escala, str) or not origem_escala.strip():
            raise ValueError(f"'origem_escala' do sprite {indice} precisa ser texto.")

        sprites.append(
            SpriteCatalogado(
                imagem=imagem,
                categoria=cast(CategoriaSprite, categoria),
                grupo=grupo,
                arquivo=arquivo,
                autor=autor,
                fonte=fonte,
                licenca=licenca,
                especie=especie,
                fragmentado=fragmentado,
                tamanho_mm=tamanho_mm,
                px_por_mm=px_por_mm,
                classe_origem=classe_origem,
                origem_escala=origem_escala,
            )
        )
        categorias_presentes.add(categoria)

    if not sprites:
        raise ValueError("O banco de sprites está vazio.")
    categorias_ausentes = set(CATEGORIAS) - categorias_presentes
    if categorias_ausentes:
        nomes = ", ".join(sorted(categorias_ausentes))
        raise ValueError(
            f"O banco precisa conter as três categorias de tamanho: {nomes}."
        )
    return tuple(sprites)


def calcular_percentual_cobertura(mascara: Image.Image) -> float:
    """Calcula a proporção coberta usando somente os pixels classificados como placa.

    Args:
        mascara: Imagem L com fundo 0, placa limpa 1 e área coberta 2.

    Returns:
        Percentual de pixels 2 entre todos os pixels da placa.

    Raises:
        ValueError: Se a máscara não contiver pixels de placa.
    """
    histograma = mascara.convert("L").histogram()
    pixels_limpos = histograma[VALORES_CLASSES["placa_limpa"]]
    pixels_cobertos = histograma[VALORES_CLASSES["placa_coberta"]]
    pixels_placa = pixels_limpos + pixels_cobertos
    if pixels_placa == 0:
        raise ValueError("A máscara não contém pixels da placa adesiva.")
    return pixels_cobertos * 100.0 / pixels_placa


def calcular_correlacao_pearson(
    valores_x: list[float], valores_y: list[float]
) -> float:
    """Calcula a correlação de Pearson para duas listas numéricas.

    Args:
        valores_x: Primeira sequência de observações.
        valores_y: Segunda sequência de observações correspondentes.

    Returns:
        Correlação no intervalo [-1, 1].

    Raises:
        ValueError: Se os comprimentos diferirem ou alguma sequência for constante.
    """
    if len(valores_x) != len(valores_y) or len(valores_x) < 2:
        raise ValueError(
            "As sequências precisam ter o mesmo tamanho e ao menos dois itens."
        )
    media_x = sum(valores_x) / len(valores_x)
    media_y = sum(valores_y) / len(valores_y)
    diferencas_x = [valor - media_x for valor in valores_x]
    diferencas_y = [valor - media_y for valor in valores_y]
    soma_x = sum(valor * valor for valor in diferencas_x)
    soma_y = sum(valor * valor for valor in diferencas_y)
    if soma_x == 0 or soma_y == 0:
        raise ValueError("A correlação não existe quando uma sequência é constante.")
    covariancia = sum(
        diferenca_x * diferenca_y
        for diferenca_x, diferenca_y in zip(diferencas_x, diferencas_y, strict=True)
    )
    return covariancia / math.sqrt(soma_x * soma_y)


def generate_sample(
    sprites: tuple[SpriteCatalogado, ...],
    percentual_alvo: float,
    idade_simulada_dias: float,
    idade_maxima_dias: float,
    rng: random.Random,
    resolucao: tuple[int, int] = RESOLUCAO_PADRAO,
    limite_sprites: int = LIMITE_SPRITES_POR_AMOSTRA,
    pesos_grupo: dict[str, float] | None = None,
    geometria_placa: GeometriaPlaca | None = None,
    rng_base: random.Random | None = None,
    rng_geometria: random.Random | None = None,
    px_por_mm: float = PX_POR_MM_PADRAO,
    k_escala_min: float = K_ESCALA_MINIMO,
    k_escala_max: float = K_ESCALA_MAXIMO,
    variacao_escala_minima: float = VARIACAO_ESCALA_MINIMA,
    variacao_escala_maxima: float = VARIACAO_ESCALA_MAXIMA,
    grade_densidade: tuple[int, int] = GRADE_DENSIDADE_PADRAO,
) -> AmostraSintetica:
    """Compõe uma cena e uma máscara de três classes com uma semente local.

    Args:
        sprites: Banco já validado com as três categorias de tamanho.
        percentual_alvo: Ocupação pretendida da superfície adesiva.
        idade_simulada_dias: Idade do refil para este exemplo.
        idade_maxima_dias: Limite usado para normalizar o envelhecimento.
        rng: Gerador aleatório exclusivo desta amostra.
        resolucao: Largura e altura da cena em pixels.
        limite_sprites: Máximo de tentativas para limitar a composição.
        pesos_grupo: Pesos normalizados usados para selecionar os grupos.
        geometria_placa: Posição e dimensões compartilhadas entre cenas.
        rng_base: Gerador separado para repetir fundo, luz e moldura.
        rng_geometria: Gerador reiniciado a cada cena de uma mesma câmera. Quando
            informado, a perspectiva e o deslocamento da captura saem dele e a
            silhueta da placa se repete entre as cenas; ruído, luz e compressão
            continuam variando por imagem.

    Returns:
        Cena RGB, máscara L e metadados derivados da máscara final.

    Raises:
        ValueError: Se o alvo, idade ou dimensões estiverem fora dos limites.
    """
    if not 0 <= percentual_alvo <= 100:
        raise ValueError("O percentual alvo precisa estar entre 0 e 100.")
    if (
        not math.isfinite(idade_simulada_dias)
        or not math.isfinite(idade_maxima_dias)
        or idade_maxima_dias <= 0
        or not 0 <= idade_simulada_dias <= idade_maxima_dias
    ):
        raise ValueError("A idade simulada precisa estar dentro da faixa configurada.")
    largura, altura = resolucao
    if largura < 100 or altura < 100 or limite_sprites < 1:
        raise ValueError(
            "Cada dimensão precisa ter ao menos 100 pixels e o limite de sprites precisa ser positivo."
        )

    if geometria_placa is None:
        geometria_placa = create_plate_geometry(resolucao, rng, px_por_mm)
    elif geometria_placa.resolucao != resolucao:
        raise ValueError("A geometria da placa precisa usar a resolução da cena.")
    caixa_placa = geometria_placa.caixa
    margem_moldura = geometria_placa.margem_moldura
    idade_relativa = idade_simulada_dias / idade_maxima_dias
    rng_cena = rng if rng_base is None else rng_base
    cena, mascara, dominante_cor, dominante_rgb = _criar_cena(
        largura,
        altura,
        caixa_placa,
        margem_moldura,
        idade_relativa,
        rng_cena,
    )
    uniao = Image.new(
        "L", (caixa_placa[2] - caixa_placa[0], caixa_placa[3] - caixa_placa[1])
    )
    k_escala = math.exp(rng.uniform(math.log(k_escala_min), math.log(k_escala_max)))
    quantidade_sprites = _compor_sprites(
        cena,
        uniao,
        caixa_placa,
        sprites,
        percentual_alvo,
        rng,
        limite_sprites,
        pesos_grupo,
        geometria_placa.px_por_mm,
        k_escala,
        variacao_escala_minima,
        variacao_escala_maxima,
        grade_densidade,
    )
    mascara.paste(VALORES_CLASSES["placa_coberta"], caixa_placa, uniao)

    rng_finalizacao = random.Random(rng.getrandbits(64))
    distratores = _selecionar_distratores(rng)
    _desenhar_distratores(cena, caixa_placa, distratores, rng)
    cena, mascara = _finalizar_cena(cena, mascara, rng_finalizacao, rng_geometria)

    percentual_cobertura_real = calcular_percentual_cobertura(mascara)
    return AmostraSintetica(
        imagem=cena.convert("RGB"),
        mascara=mascara,
        percentual_cobertura_real=percentual_cobertura_real,
        n_sprites=quantidade_sprites,
        distratores_presentes=distratores,
        dominante_cor=dominante_cor,
        dominante_rgb=dominante_rgb,
        alvo_atingido=abs(percentual_cobertura_real - percentual_alvo)
        <= TOLERANCIA_COBERTURA_PP + 1e-9,
        px_por_mm=geometria_placa.px_por_mm,
        k_escala=k_escala,
    )


def _dividir_placas_reais(
    diretorio: Path,
    semente: int,
    proporcao_avaliacao: float,
) -> tuple[list[Path], list[Path]]:
    """Separa os identificadores das placas antes de carregar qualquer máscara."""
    pasta_imagens = diretorio / "imagens"
    pasta_mascaras = diretorio / "mascaras"
    if not pasta_imagens.is_dir() or not pasta_mascaras.is_dir():
        raise FileNotFoundError(
            f"O conjunto real precisa conter imagens/ e mascaras/: {diretorio}."
        )
    imagens = sorted(
        caminho
        for caminho in pasta_imagens.iterdir()
        if caminho.is_file() and caminho.suffix.lower() in {".png", ".jpg", ".jpeg"}
    )
    mascaras = {
        caminho.stem: caminho
        for caminho in pasta_mascaras.iterdir()
        if caminho.is_file() and caminho.suffix.lower() in {".png", ".jpg", ".jpeg"}
    }
    faltantes = [caminho.stem for caminho in imagens if caminho.stem not in mascaras]
    sem_imagem = sorted(set(mascaras) - {caminho.stem for caminho in imagens})
    if not imagens or faltantes or sem_imagem:
        raise ValueError(
            "Imagens e máscaras precisam formar pares completos; "
            f"sem máscara={faltantes[:3]}, sem imagem={sem_imagem[:3]}."
        )
    if len(imagens) < 2:
        raise ValueError("A separação exige pelo menos duas placas reais.")

    quantidade_avaliacao = max(1, round(len(imagens) * proporcao_avaliacao))
    quantidade_avaliacao = min(len(imagens) - 1, quantidade_avaliacao)
    nomes = {caminho.stem for caminho in imagens}
    bases_forcadas = {Path(nome).stem for nome in NOMES_BASES_REAIS} & nomes
    quantidade_composicao = len(imagens) - quantidade_avaliacao
    if len(bases_forcadas) > quantidade_composicao:
        raise ValueError("Há mais bases obrigatórias do que placas de composição.")

    restantes = sorted(nomes - bases_forcadas)
    random.Random(semente).shuffle(restantes)
    composicao = bases_forcadas | set(
        restantes[: quantidade_composicao - len(bases_forcadas)]
    )
    avaliacao = nomes - composicao
    por_nome = {caminho.stem: caminho for caminho in imagens}
    return (
        [por_nome[nome] for nome in sorted(composicao)],
        [por_nome[nome] for nome in sorted(avaliacao)],
    )


def _carregar_base_real(
    caminho_imagem: Path,
    diretorio: Path,
    resolucao: tuple[int, int],
    diretorio_mascaras: Path | None = None,
) -> BasePlacaReal:
    import numpy as np

    caminho_mascara = (
        diretorio_mascaras or diretorio / "mascaras"
    ) / f"{caminho_imagem.stem}.png"
    if diretorio_mascaras is not None and not caminho_mascara.is_file():
        raise FileNotFoundError(f"Máscara complementar ausente: {caminho_mascara}.")
    if not caminho_mascara.is_file():
        caminho_mascara = next(
            (
                candidato
                for candidato in (".jpg", ".jpeg")
                if (
                    diretorio / "mascaras" / f"{caminho_imagem.stem}{candidato}"
                ).is_file()
            ),
            None,
        )
        if caminho_mascara is None:
            raise FileNotFoundError(f"Máscara ausente para {caminho_imagem.name}.")
        caminho_mascara = (
            diretorio / "mascaras" / f"{caminho_imagem.stem}{caminho_mascara}"
        )

    with Image.open(caminho_imagem) as origem:
        imagem = origem.convert("RGB")
    with Image.open(caminho_mascara) as origem:
        mascara = origem.convert("L")
    if imagem.size != mascara.size:
        raise ValueError(f"Dimensões divergentes em {caminho_imagem.stem}.")
    if imagem.size != resolucao:
        imagem = imagem.resize(resolucao, Image.Resampling.BILINEAR)
        mascara = mascara.resize(resolucao, Image.Resampling.NEAREST)
    valores = set(np.unique(np.asarray(mascara)).tolist())
    if not valores <= {0, 1, 2, 255}:
        raise ValueError(f"Máscara de {caminho_imagem.stem} tem classes inválidas.")
    classes = np.asarray(mascara, dtype=np.uint8)
    area_placa = int(np.count_nonzero((classes == 1) | (classes == 2)))
    if area_placa == 0:
        raise ValueError(f"A placa de {caminho_imagem.stem} está vazia.")
    cobertura = 100.0 * np.count_nonzero(classes == 2) / area_placa
    return BasePlacaReal(caminho_imagem.stem, imagem, mascara, cobertura)


def _particionar_fontes(
    placas: list[Path],
    semente: int,
    bases_elegiveis: set[str] | None = None,
) -> dict[str, list[Path]]:
    """Atribui origens e bases a conjuntos disjuntos antes de abrir os pixels."""
    if len(placas) < 3:
        raise ValueError(
            "São necessárias três placas de composição para separar os conjuntos."
        )
    nomes_bases = (
        {Path(nome).stem for nome in NOMES_BASES_REAIS}
        if bases_elegiveis is None
        else set(bases_elegiveis)
    )
    bases = [p for p in placas if p.stem in nomes_bases]
    if not bases:
        raise ValueError("Nenhuma base real elegível está na composição.")
    restantes = [p for p in placas if p.stem not in nomes_bases]
    rng = random.Random(semente ^ 0xF07E5)
    rng.shuffle(bases)
    rng.shuffle(restantes)
    grupos: dict[str, list[Path]] = {
        nome: [] for nome in ("treino", "validacao", "teste")
    }
    proporcoes = (0.70, 0.15, 0.15)
    metas_fontes = [
        max(1, math.floor(len(placas) * proporcao + 0.5)) for proporcao in proporcoes
    ]
    while sum(metas_fontes) > len(placas):
        indice = max(range(3), key=lambda i: metas_fontes[i])
        if metas_fontes[indice] <= 1:
            raise ValueError("Não há placas suficientes para separar três conjuntos.")
        metas_fontes[indice] -= 1
    while sum(metas_fontes) < len(placas):
        metas_fontes[0] += 1

    quantidade_bases = len(bases)
    metas_bases = [
        max(1, math.floor(quantidade_bases * proporcao + 0.5))
        for proporcao in proporcoes
    ]
    while sum(metas_bases) > quantidade_bases:
        indice = max(range(3), key=lambda i: metas_bases[i])
        if metas_bases[indice] <= 1:
            metas_bases[indice] -= 1
            continue
        metas_bases[indice] -= 1
    while sum(metas_bases) < quantidade_bases:
        metas_bases[0] += 1

    inicio = 0
    for nome, quantidade in zip(grupos, metas_bases, strict=True):
        grupos[nome].extend(bases[inicio : inicio + quantidade])
        inicio += quantidade
    indice_restante = 0
    for indice, nome in enumerate(grupos):
        quantidade = metas_fontes[indice] - len(grupos[nome])
        grupos[nome].extend(restantes[indice_restante : indice_restante + quantidade])
        indice_restante += quantidade
    return {nome: sorted(lista) for nome, lista in grupos.items()}


def _extrair_recortes_reais(
    bases: tuple[BasePlacaReal, ...],
) -> tuple[list[RecorteInsetoReal], dict[str, int], dict[str, int]]:
    """Recorta apenas as placas de composição, preservando a alfa da classe 2."""
    import cv2
    import numpy as np

    recortes: list[RecorteInsetoReal] = []
    componentes_por_placa: dict[str, int] = {}
    aceitos_por_placa: dict[str, int] = {}
    for base in bases:
        mascara = np.asarray(base.mascara, dtype=np.uint8)
        quantidade, rotulos, estatisticas, _ = cv2.connectedComponentsWithStats(
            (mascara == VALORES_CLASSES["placa_coberta"]).astype(np.uint8),
            connectivity=8,
        )
        componentes_por_placa[base.identificador] = quantidade - 1
        aceitos = 0
        for indice in range(1, quantidade):
            x, y, largura, altura, area = estatisticas[indice]
            if area < AREA_MINIMA_RECORTE_REAL:
                continue
            proporcao = max(largura / altura, altura / largura)
            if proporcao > PROPORCAO_MAXIMA_RECORTE_REAL:
                continue
            alfa = (rotulos[y : y + altura, x : x + largura] == indice).astype(
                np.uint8
            ) * 255
            recorte = base.imagem.crop((x, y, x + largura, y + altura)).convert("RGBA")
            recorte.putalpha(Image.fromarray(alfa, mode="L"))
            recortes.append(
                RecorteInsetoReal(
                    identificador=f"{base.identificador}__cc{indice:04d}",
                    placa_origem=base.identificador,
                    imagem=recorte,
                    area_px=int(area),
                )
            )
            aceitos += 1
        aceitos_por_placa[base.identificador] = aceitos
    if not recortes:
        raise ValueError("Nenhum componente de inseto passou pelos filtros de recorte.")
    return recortes, componentes_por_placa, aceitos_por_placa


def _carregar_recortes_coco(
    diretorio: Path, placas_permitidas: set[str]
) -> tuple[list[RecorteInsetoReal], dict[str, int], dict[str, int]]:
    """Carrega somente recortes SAM aprovados de placas do conjunto permitido."""
    import numpy as np

    raiz = diretorio.resolve()
    recortes: list[RecorteInsetoReal] = []
    encontrados = {nome: 0 for nome in sorted(placas_permitidas)}
    aceitos = {nome: 0 for nome in sorted(placas_permitidas)}
    for nome in sorted(placas_permitidas):
        catalogo = raiz / "catalogos" / f"{nome}.jsonl"
        if not catalogo.is_file():
            raise FileNotFoundError(f"Catálogo de recortes ausente: {catalogo}.")
        for linha in catalogo.read_text("utf-8").splitlines():
            if not linha.strip():
                continue
            registro = json.loads(linha)
            if registro.get("placa_origem") != nome:
                raise ValueError(f"Proveniência divergente no catálogo {catalogo}.")
            encontrados[nome] += 1
            if not registro.get("aprovada") or not registro.get("arquivo"):
                continue
            caminho = (raiz / registro["arquivo"]).resolve()
            if not caminho.is_relative_to(raiz) or not caminho.is_file():
                raise ValueError(f"Recorte fora da biblioteca ou ausente: {caminho}.")
            with Image.open(caminho) as aberta:
                imagem = aberta.convert("RGBA")
            alfa = np.asarray(imagem.getchannel("A"), dtype=np.uint8)
            area = int(np.count_nonzero(alfa))
            if area == 0 or area != int(registro.get("area_projetada_px", -1)):
                imagem.close()
                raise ValueError(f"Alfa divergente do catálogo: {caminho}.")
            id_coco = str(registro["anotacao_coco_id"])
            recortes.append(
                RecorteInsetoReal(
                    identificador=f"{nome}__coco{id_coco}",
                    placa_origem=nome,
                    imagem=imagem,
                    area_px=area,
                    anotacao_coco_id=id_coco,
                    taxon=registro.get("taxon"),
                    sha256_conteudo=_sha256_arquivo(caminho),
                )
            )
            aceitos[nome] += 1
    if not recortes:
        raise ValueError("Nenhum recorte COCO/SAM aprovado nas placas permitidas.")
    return recortes, encontrados, aceitos


def _criar_base_sintetica(
    resolucao: tuple[int, int],
    rng: random.Random,
) -> tuple[Image.Image, Image.Image]:
    """Cria uma base StickFly K-45 lisa, sem grade ou insetos desenhados."""
    import numpy as np

    largura, altura = resolucao
    imagem = Image.new("RGB", resolucao, (239, 240, 238))
    desenho = ImageDraw.Draw(imagem)
    margem_x = max(8, round(largura * 0.055))
    margem_y = max(8, round(altura * 0.12))
    largura_placa = min(
        largura - margem_x * 2,
        round((altura - margem_y * 2) * 450 / 220),
    )
    altura_placa = round(largura_placa * 220 / 450)
    x0 = (largura - largura_placa) // 2
    y0 = (altura - altura_placa) // 2
    borda = max(3, round(min(largura, altura) * 0.018))
    caixa_externa = (
        max(0, x0 - borda),
        max(0, y0 - borda),
        min(largura - 1, x0 + largura_placa + borda),
        min(altura - 1, y0 + altura_placa + borda),
    )
    desenho.rectangle(caixa_externa, fill=(184, 185, 180))
    desenho.rectangle(
        (x0, y0, x0 + largura_placa - 1, y0 + altura_placa - 1),
        fill=(232, 230, 221),
    )

    superficie = np.full(
        (altura_placa, largura_placa, 3), (232, 230, 221), dtype=np.float32
    )
    eixo_x = np.minimum(np.arange(largura_placa), np.arange(largura_placa)[::-1])
    eixo_y = np.minimum(np.arange(altura_placa), np.arange(altura_placa)[::-1])
    distancia_borda = np.minimum(eixo_y[:, None], eixo_x[None, :])
    peso_amarelo = 0.55 * np.exp(
        -distancia_borda / max(1.0, min(largura_placa, altura_placa) * 0.10)
    )
    amarelo = np.asarray((206, 194, 152), dtype=np.float32)
    superficie = (
        superficie * (1 - peso_amarelo[..., None]) + amarelo * peso_amarelo[..., None]
    )
    gerador_ruido = np.random.default_rng(rng.getrandbits(64))
    ruido = gerador_ruido.normal(0.0, 4.0, (altura_placa, largura_placa, 1))
    superficie = np.clip(superficie + 0.10 * ruido, 0, 255).astype(np.uint8)
    pixels = np.asarray(imagem).copy()
    pixels[y0 : y0 + altura_placa, x0 : x0 + largura_placa] = superficie
    mascara = np.zeros((altura, largura), dtype=np.uint8)
    mascara[y0 : y0 + altura_placa, x0 : x0 + largura_placa] = 1
    return Image.fromarray(pixels, mode="RGB"), Image.fromarray(mascara, mode="L")


def _ordenar_recortes_por_reuso(
    usos_globais: list[int],
    rng: random.Random,
) -> list[int]:
    """Prioriza recortes menos usados e randomiza recortes empatados."""
    por_uso: dict[int, list[int]] = defaultdict(list)
    for indice, usos in enumerate(usos_globais):
        por_uso[usos].append(indice)
    ordem: list[int] = []
    for usos in sorted(por_uso):
        grupo = por_uso[usos]
        rng.shuffle(grupo)
        ordem.extend(grupo)
    return ordem


def _amostrar_centro_placa(
    erodida: object,
    centros_validos: object,
    focos: list[tuple[int, int]],
    probabilidade_cluster: float,
    rng: random.Random,
    regiao_cluster: object,
) -> tuple[int, int]:
    if focos and rng.random() < probabilidade_cluster:
        centro_x, centro_y = rng.choice(focos)
        altura, largura = erodida.shape
        for _ in range(24):
            x = round(rng.gauss(centro_x, max(2, largura * 0.11)))
            y = round(rng.gauss(centro_y, max(2, altura * 0.12)))
            if (
                0 <= x < largura
                and 0 <= y < altura
                and erodida[y, x]
                and regiao_cluster[y, x]
            ):
                return x, y
    y, x = centros_validos[rng.randrange(len(centros_validos))]
    return int(x), int(y)


def _transformar_recorte_real(
    recorte: Image.Image,
    rng: random.Random,
    fator_escala: float = 1.0,
) -> Image.Image:
    """Escala calibrada e aplica giros ortogonais com máscara binária preservada."""
    imagem = recorte.copy()
    if fator_escala != 1.0:
        tamanho = tuple(max(1, round(lado * fator_escala)) for lado in imagem.size)
        rgb = imagem.convert("RGB").resize(tamanho, Image.Resampling.BILINEAR)
        alfa = imagem.getchannel("A").resize(tamanho, Image.Resampling.NEAREST)
        imagem.close()
        imagem = Image.merge("RGBA", (*rgb.split(), alfa))
        rgb.close()
        alfa.close()
    rotacoes = (
        None,
        Image.Transpose.ROTATE_90,
        Image.Transpose.ROTATE_180,
        Image.Transpose.ROTATE_270,
    )
    rotacao = rotacoes[rng.randrange(4)]
    if rotacao is not None:
        imagem = imagem.transpose(rotacao)
    if rng.random() < 0.5:
        imagem = imagem.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    return imagem


def _colar_recorte_real(
    imagem: object,
    coberta: object,
    placa: object,
    inseto: Image.Image,
    centro_x: int,
    centro_y: int,
) -> tuple[int, int, object]:
    import numpy as np

    pixels = np.asarray(inseto, dtype=np.uint8)
    alfa = pixels[:, :, 3] > 0
    inicio_x = centro_x - inseto.width // 2
    inicio_y = centro_y - inseto.height // 2
    fim_x = inicio_x + inseto.width
    fim_y = inicio_y + inseto.height
    altura, largura = coberta.shape
    x0, y0 = max(0, inicio_x), max(0, inicio_y)
    x1, y1 = min(largura, fim_x), min(altura, fim_y)
    sx0, sy0 = x0 - inicio_x, y0 - inicio_y
    sx1, sy1 = sx0 + x1 - x0, sy0 + y1 - y0
    alfa_local = alfa[sy0:sy1, sx0:sx1]
    alfa_placa = alfa_local & placa[y0:y1, x0:x1]
    recorte_rgb = pixels[sy0:sy1, sx0:sx1, :3]
    regiao_imagem = imagem[y0:y1, x0:x1]
    regiao_imagem[alfa_placa] = recorte_rgb[alfa_placa]
    coberta[y0:y1, x0:x1] |= alfa_placa
    return x0, y0, alfa_placa


def _bases_compativeis_com_alvo(
    bases: list[BasePlacaReal],
    percentual_alvo: float,
    aglomeracao_por_base: dict[str, float],
) -> list[BasePlacaReal]:
    """Evita bases com foco escuro herdado em coberturas abaixo de 20%."""
    if percentual_alvo >= 20.0:
        return bases
    filtradas = [
        base
        for base in bases
        if aglomeracao_por_base.get(base.identificador, 1.0)
        <= LIMITE_AGLOMERACAO_BASE_BAIXA_COBERTURA
    ]
    return filtradas or bases


def _compor_recortes_reais(
    imagem_base: Image.Image,
    mascara_base: Image.Image,
    recortes: list[RecorteInsetoReal],
    percentual_alvo: float,
    rng: random.Random,
    limite_colagens: int,
    limite_reuso: int,
    intensidade_aglomeracao: float,
    usos_globais: list[int],
    fator_escala: float = 1.0,
) -> tuple[Image.Image, Image.Image, dict[str, object]]:
    """Cola recortes exatos dentro da placa e devolve as áreas medidas."""
    import cv2
    import numpy as np

    imagem = np.asarray(imagem_base.convert("RGB"), dtype=np.uint8).copy()
    classes = np.asarray(mascara_base.convert("L"), dtype=np.uint8)
    placa = (classes == 1) | (classes == 2)
    herdada = (classes == VALORES_CLASSES["placa_coberta"]) & placa
    coberta = herdada.copy()
    area_placa = int(placa.sum())
    if area_placa == 0:
        raise ValueError("A base escolhida não contém uma placa identificável.")

    largura, altura = mascara_base.size
    raio_x = max(1, round(EROSAO_PLACA_PX * largura / LARGURA_MODELO))
    raio_y = max(1, round(EROSAO_PLACA_PX * altura / ALTURA_MODELO))
    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE,
        (raio_x * 2 + 1, raio_y * 2 + 1),
    )
    # Uma região sem supervisão não é uma borda física da placa. Erodir cada
    # mancha ignorada criaria grandes buracos artificiais na área de composição.
    erodida = cv2.erode(placa.astype(np.uint8), kernel, iterations=1).astype(bool)
    centros_validos = np.argwhere(erodida)
    if len(centros_validos) == 0:
        raise ValueError("A placa ficou vazia após a erosão da margem adesiva.")

    minimo_y, minimo_x = centros_validos.min(axis=0)
    maximo_y, maximo_x = centros_validos.max(axis=0)
    faixa_x = max(1, int(maximo_x - minimo_x + 1))
    faixa_y = max(1, int(maximo_y - minimo_y + 1))
    raio_foco_x = max(1, round(faixa_x * FRACAO_RAIO_FOCO_LARGURA))
    raio_foco_y = max(1, round(faixa_y * FRACAO_RAIO_FOCO_ALTURA))
    focos: list[tuple[int, int]] = []
    numero_focos = max(
        NUMERO_MINIMO_FOCOS,
        min(NUMERO_MAXIMO_FOCOS, round(4 + percentual_alvo / 25)),
    )
    distancia_minima_focos = min(faixa_x, faixa_y) * 0.30
    for _ in range(numero_focos):
        for _ in range(256):
            y_foco, x_foco = centros_validos[rng.randrange(len(centros_validos))]
            candidato = (int(x_foco), int(y_foco))
            if all(
                math.hypot(candidato[0] - x, candidato[1] - y) >= distancia_minima_focos
                for x, y in focos
            ):
                focos.append(candidato)
                break
        else:
            y_foco, x_foco = centros_validos[rng.randrange(len(centros_validos))]
            focos.append((int(x_foco), int(y_foco)))

    regiao_aglomeracao = np.zeros_like(erodida)
    yy, xx = np.ogrid[:altura, :largura]
    for centro_x, centro_y in focos:
        elipse = ((xx - centro_x) / raio_foco_x) ** 2 + (
            (yy - centro_y) / raio_foco_y
        ) ** 2 <= 1.0
        regiao_aglomeracao |= elipse & erodida
    centros_aglomeracao = np.argwhere(regiao_aglomeracao)
    if not len(centros_aglomeracao):
        regiao_aglomeracao = erodida.copy()
        centros_aglomeracao = centros_validos

    raio_separacao = round(
        EROSAO_PLACA_PX * largura / LARGURA_MODELO * FRACAO_MARGEM_DISPERSAO
    )
    margem = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE,
        (raio_separacao * 2 + 1, raio_separacao * 2 + 1),
    )
    regiao_dispersao = erodida & ~cv2.dilate(
        regiao_aglomeracao.astype(np.uint8), margem, iterations=1
    ).astype(bool)
    centros_dispersos = np.argwhere(regiao_dispersao)
    if not len(centros_dispersos):
        centros_dispersos = centros_validos
    if intensidade_aglomeracao == 0:
        centros_aglomeracao = np.empty((0, 2), dtype=np.int32)
        centros_dispersos = centros_validos

    ordem_recortes = _ordenar_recortes_por_reuso(usos_globais, rng)
    ha_recortes_aglomerados = any(
        max(registro.imagem.size) > LADO_MAXIMO_RECORTE_DISPERSO
        for registro in recortes
    )
    usos_amostra: dict[int, int] = {}
    indices_pequenos = {
        indice
        for indice, registro in enumerate(recortes)
        if max(registro.imagem.size) <= LADO_MAXIMO_RECORTE_DISPERSO
    }
    usos_pequenos = 0
    placas_origem: set[str] = set()
    selecionados: list[int] = []
    indice_ordem = 0

    def proximo_recorte(*, pequeno: bool = False, qualquer: bool = False) -> int | None:
        nonlocal indice_ordem
        indice_recorte: int | None = None
        for _ in range(len(ordem_recortes)):
            candidato = ordem_recortes[indice_ordem % len(ordem_recortes)]
            indice_ordem += 1
            if usos_amostra.get(candidato, 0) < limite_reuso and (
                qualquer
                or (
                    not pequeno
                    and (
                        max(recortes[candidato].imagem.size)
                        > LADO_MAXIMO_RECORTE_DISPERSO
                        or not ha_recortes_aglomerados
                    )
                )
                or (
                    pequeno
                    and (
                        max(recortes[candidato].imagem.size)
                        <= LADO_MAXIMO_RECORTE_DISPERSO
                        or (
                            intensidade_aglomeracao == 0
                            and usos_pequenos >= len(indices_pequenos) * limite_reuso
                        )
                    )
                )
            ):
                indice_recorte = candidato
                break
        return indice_recorte

    def reservar_recorte(indice_recorte: int) -> RecorteInsetoReal:
        nonlocal usos_pequenos
        usos_amostra[indice_recorte] = usos_amostra.get(indice_recorte, 0) + 1
        if indice_recorte in indices_pequenos:
            usos_pequenos += 1
        selecionados.append(indice_recorte)
        registro = recortes[indice_recorte]
        placas_origem.add(registro.placa_origem)
        return registro

    area_alvo = round(percentual_alvo * area_placa / 100.0)
    area_nova_alvo = max(0, area_alvo - int(herdada.sum()))
    area_aglomerada_alvo = round(area_nova_alvo * intensidade_aglomeracao)
    area_dispersao_alvo = max(0, area_nova_alvo - area_aglomerada_alvo)
    mascara_aglomerada = np.zeros_like(coberta)
    mascara_dispersos = np.zeros_like(coberta)
    tentativas = 0
    recortes_aglomerados = [
        registro.area_px
        for registro in recortes
        if max(registro.imagem.size) > LADO_MAXIMO_RECORTE_DISPERSO
    ]
    recortes_dispersos = [
        registro.area_px
        for registro in recortes
        if max(registro.imagem.size) <= LADO_MAXIMO_RECORTE_DISPERSO
    ]
    if not recortes_aglomerados:
        recortes_aglomerados = [registro.area_px for registro in recortes]
    if not recortes_dispersos:
        recortes_dispersos = [registro.area_px for registro in recortes]
    tentativas_aglomeradas_estimadas = area_aglomerada_alvo / max(
        1.0,
        sum(recortes_aglomerados)
        / len(recortes_aglomerados)
        * EFICIENCIA_AREA_AGLOMERADA,
    )
    tentativas_dispersas_estimadas = area_dispersao_alvo / max(
        1.0,
        sum(recortes_dispersos) / len(recortes_dispersos) * EFICIENCIA_AREA_DISPERSA,
    )
    tentativas_estimadas = (
        tentativas_aglomeradas_estimadas + tentativas_dispersas_estimadas
    )
    intensidade_contagem = (
        tentativas_aglomeradas_estimadas / tentativas_estimadas
        if tentativas_estimadas
        else intensidade_aglomeracao
    )
    limite_tentativas_aglomeradas = min(
        limite_colagens,
        max(0, math.ceil(limite_colagens * intensidade_contagem)),
    )
    while (
        tentativas < limite_tentativas_aglomeradas
        and int((mascara_aglomerada & ~herdada).sum()) < area_aglomerada_alvo
    ):
        indice_recorte = proximo_recorte()
        if indice_recorte is None:
            break
        registro = reservar_recorte(indice_recorte)
        inseto = _transformar_recorte_real(registro.imagem, rng, fator_escala)
        centro_x, centro_y = _amostrar_centro_placa(
            erodida,
            centros_aglomeracao,
            focos,
            1.0,
            rng,
            regiao_aglomeracao,
        )
        x0, y0, alfa_placa = _colar_recorte_real(
            imagem, coberta, placa, inseto, centro_x, centro_y
        )
        mascara_aglomerada[
            y0 : y0 + alfa_placa.shape[0], x0 : x0 + alfa_placa.shape[1]
        ] |= alfa_placa
        tentativas += 1

    area_alvo_com_tolerancia = max(
        0, math.ceil((percentual_alvo - TOLERANCIA_RECOMPOSICAO_PP) * area_placa / 100)
    )
    distancia_a_cobertura = cv2.distanceTransform(
        (placa & ~coberta).astype(np.uint8), cv2.DIST_L2, 5
    )
    centros_isolados: list[tuple[int, int, int]] = []
    distribuicao_uniforme_trocar = (
        intensidade_aglomeracao == 0 and percentual_alvo >= 20.0
    )
    if distribuicao_uniforme_trocar:
        while (
            tentativas < limite_colagens
            and int(coberta.sum()) < area_alvo_com_tolerancia
        ):
            indice_recorte = proximo_recorte(pequeno=True)
            if indice_recorte is None:
                break
            registro = reservar_recorte(indice_recorte)
            inseto = _transformar_recorte_real(registro.imagem, rng, fator_escala)
            y, x = centros_validos[rng.randrange(len(centros_validos))]
            _colar_recorte_real(imagem, coberta, placa, inseto, int(x), int(y))
            tentativas += 1
    while (
        tentativas < limite_colagens
        and int(coberta.sum()) < area_alvo_com_tolerancia
        and int(mascara_dispersos.sum()) < area_dispersao_alvo
        and not distribuicao_uniforme_trocar
    ):
        indice_recorte = proximo_recorte(pequeno=True)
        if indice_recorte is None:
            break
        registro = recortes[indice_recorte]
        inseto = _transformar_recorte_real(registro.imagem, rng, fator_escala)
        raio = max(1, max(inseto.size) // 3) + 1
        margem_grupos = max(2, max(inseto.size) // DIVISOR_ESPACAMENTO_DISPERSO)
        centro_isolado: tuple[int, int] | None = None
        for _ in range(256):
            y, x = centros_dispersos[rng.randrange(len(centros_dispersos))]
            x, y = int(x), int(y)
            if distancia_a_cobertura[y, x] <= margem_grupos:
                continue
            if any(
                math.hypot(x - outro_x, y - outro_y) <= raio + outro_raio
                for outro_x, outro_y, outro_raio in centros_isolados
            ):
                continue
            centro_isolado = (x, y)
            break
        if centro_isolado is None:
            break
        reservar_recorte(indice_recorte)
        centro_x, centro_y = centro_isolado
        x0, y0, alfa_placa = _colar_recorte_real(
            imagem, coberta, placa, inseto, centro_x, centro_y
        )
        mascara_dispersos[
            y0 : y0 + alfa_placa.shape[0], x0 : x0 + alfa_placa.shape[1]
        ] |= alfa_placa
        centros_isolados.append((centro_x, centro_y, raio))
        tentativas += 1

    # Para alvos menores, relaxa o espaçamento antes de encerrar a composição.
    while (
        tentativas < limite_colagens
        and int(coberta.sum()) < area_alvo_com_tolerancia
        and not distribuicao_uniforme_trocar
    ):
        indice_recorte = proximo_recorte(
            pequeno=intensidade_aglomeracao == 0,
            qualquer=intensidade_aglomeracao != 0,
        )
        if indice_recorte is None:
            break
        registro = reservar_recorte(indice_recorte)
        inseto = _transformar_recorte_real(registro.imagem, rng, fator_escala)
        if intensidade_aglomeracao == 0:
            y, x = centros_validos[rng.randrange(len(centros_validos))]
            _colar_recorte_real(imagem, coberta, placa, inseto, int(x), int(y))
        else:
            borda_coberta = cv2.dilate(
                coberta.astype(np.uint8), np.ones((9, 9), np.uint8)
            ).astype(bool)
            candidatos = np.argwhere(erodida & ~coberta & borda_coberta)
            if not len(candidatos):
                candidatos = np.argwhere(erodida & ~coberta)
            if not len(candidatos):
                break
            y, x = candidatos[rng.randrange(len(candidatos))]
            _colar_recorte_real(imagem, coberta, placa, inseto, int(x), int(y))
        tentativas += 1

    classes_finais = np.zeros_like(classes)
    classes_finais[classes == 255] = 255
    classes_finais[placa] = VALORES_CLASSES["placa_limpa"]
    classes_finais[coberta] = VALORES_CLASSES["placa_coberta"]
    area_herdada = int(herdada.sum())
    area_final = int(coberta.sum())
    adicionada = area_final - area_herdada
    percentual_real = 100.0 * area_final / area_placa
    n, _, estatisticas, _ = cv2.connectedComponentsWithStats(
        coberta.astype(np.uint8), connectivity=8
    )
    area_aglomerada = sum(
        int(estatisticas[indice, cv2.CC_STAT_AREA])
        for indice in range(1, n)
        if int(estatisticas[indice, cv2.CC_STAT_AREA]) > AREA_COMPONENTE_AGLOMERADO
    )
    fracao_aglomerada = area_aglomerada / area_final if area_final else 0.0
    metadados: dict[str, object] = {
        "_indices_recortes_usados": selecionados,
        "recortes_coco_ids_usados": [
            recortes[indice].identificador for indice in selecionados
        ],
        "taxons_recortes_usados": sorted(
            {
                recortes[indice].taxon
                for indice in selecionados
                if recortes[indice].taxon
            }
        ),
        "n_recortes": len(selecionados),
        "cobertura_herdada_base_percentual": 100.0 * area_herdada / area_placa,
        "cobertura_adicionada_percentual": 100.0 * adicionada / area_placa,
        "percentual_cobertura_real": percentual_real,
        "fracao_aglomerada": fracao_aglomerada,
        "maior_reuso_recorte_na_amostra": max(usos_amostra.values(), default=0),
        "placas_origem_recortes": sorted(placas_origem),
    }
    return (
        Image.fromarray(imagem, mode="RGB"),
        Image.fromarray(classes_finais, mode="L"),
        metadados,
    )


def generate_dataset(
    configuracao: ConfiguracaoDataset,
    sprites: tuple[SpriteCatalogado, ...] = (),
    parar_apos: int | None = None,
) -> list[dict[str, object]]:
    """Gera imagens, máscaras e metadados em uma estrutura estável.

    Args:
        configuracao: Semente, volume, idade máxima e diretório de saída.
        sprites: Banco catalogado e validado usado nas composições.

    Returns:
        Registros JSONL em ordem de identificador.

    Raises:
        FileExistsError: Se o diretório de saída já contiver arquivos.
        OSError: Se não for possível criar ou gravar os artefatos.
    """
    if configuracao.diretorio_placas_reais is not None:
        return _gerar_dataset_recomposicao_real(configuracao, parar_apos)
    if parar_apos is not None:
        raise ValueError("--parar-apos só é válido na recomposição de placas reais.")
    if not sprites:
        raise ValueError("Informe sprites ou o diretório de placas reais.")
    saida = configuracao.diretorio_saida.resolve()
    if saida.exists() and any(saida.iterdir()):
        raise FileExistsError(f"O diretório de saída não está vazio: {saida}.")
    diretorio_imagens = saida / "imagens"
    diretorio_mascaras = saida / "mascaras"
    diretorio_imagens.mkdir(parents=True, exist_ok=True)
    diretorio_mascaras.mkdir(parents=True, exist_ok=True)

    rng_global = random.Random(configuracao.semente)
    pesos_grupo = _normalizar_pesos_grupo(
        {sprite.grupo for sprite in sprites},
        configuracao.pesos_grupo or PESOS_GRUPO_PADRAO,
    )
    sementes = [rng_global.getrandbits(64) for _ in range(configuracao.quantidade)]
    faixas = _criar_faixas_estratificadas(configuracao.quantidade, configuracao.semente)
    divisoes = _criar_divisoes(configuracao.quantidade, configuracao.semente)
    registros: list[dict[str, object]] = []

    caminho_metadados = saida / "metadados.jsonl"
    with caminho_metadados.open(
        "w", encoding="utf-8", newline="\n"
    ) as arquivo_metadados:
        for indice, semente_amostra in enumerate(sementes):
            rng = random.Random(semente_amostra)
            rng_cobertura = random.Random(semente_amostra ^ 0xC0B3A7)
            rng_idade = random.Random(semente_amostra ^ 0xA61DADE)
            nome_faixa, minimo, maximo = FAIXAS_COBERTURA[faixas[indice]]
            percentual_alvo = rng_cobertura.uniform(minimo, maximo)
            idade_simulada = rng_idade.uniform(0.0, configuracao.idade_maxima_dias)
            amostra = generate_sample(
                sprites=sprites,
                percentual_alvo=percentual_alvo,
                idade_simulada_dias=idade_simulada,
                idade_maxima_dias=configuracao.idade_maxima_dias,
                rng=rng,
                resolucao=configuracao.resolucao,
                limite_sprites=configuracao.limite_sprites,
                pesos_grupo=pesos_grupo,
                px_por_mm=configuracao.px_por_mm,
                k_escala_min=configuracao.k_escala_min,
                k_escala_max=configuracao.k_escala_max,
                variacao_escala_minima=configuracao.variacao_escala_minima,
                variacao_escala_maxima=configuracao.variacao_escala_maxima,
                grade_densidade=configuracao.grade_densidade,
            )

            identificador = f"amostra_{indice + 1:06d}"
            amostra.imagem.save(
                diretorio_imagens / f"{identificador}.png", format="PNG"
            )
            amostra.mascara.save(
                diretorio_mascaras / f"{identificador}.png",
                format="PNG",
            )
            registro: dict[str, object] = {
                "id": identificador,
                "semente": semente_amostra,
                "conjunto": divisoes[indice],
                "faixa_cobertura_alvo": nome_faixa,
                "percentual_cobertura_alvo": percentual_alvo,
                "percentual_cobertura_real": amostra.percentual_cobertura_real,
                "alvo_atingido": amostra.alvo_atingido,
                "idade_simulada_dias": idade_simulada,
                "px_por_mm": amostra.px_por_mm,
                "k_escala": amostra.k_escala,
                "n_sprites": amostra.n_sprites,
                "distratores_presentes": amostra.distratores_presentes,
                "dominante_cor": amostra.dominante_cor,
                "dominante_rgb": list(amostra.dominante_rgb),
                "mascara_classes": VALORES_CLASSES,
                "pesos_grupo": pesos_grupo,
            }
            registros.append(registro)
            arquivo_metadados.write(
                json.dumps(
                    registro, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                )
                + "\n"
            )

    registro_execucao = {
        "semente_global": configuracao.semente,
        "quantidade": configuracao.quantidade,
        "idade_maxima_dias": configuracao.idade_maxima_dias,
        "resolucao": list(configuracao.resolucao),
        "dimensoes_refil_mm": list(DIMENSOES_REFIL_MM),
        "px_por_mm_referencia": configuracao.px_por_mm,
        "faixa_k_escala": [configuracao.k_escala_min, configuracao.k_escala_max],
        "variacao_escala_inseto": [
            configuracao.variacao_escala_minima,
            configuracao.variacao_escala_maxima,
        ],
        "grade_densidade": list(configuracao.grade_densidade),
        "limite_sprites": configuracao.limite_sprites,
        "pesos_grupo": pesos_grupo,
        "tentativas_por_sprite": TENTATIVAS_POR_SPRITE,
        "tolerancia_cobertura_pp": TOLERANCIA_COBERTURA_PP,
        "versao_python": platform.python_version(),
        "versao_pillow": PIL.__version__,
        "catalogo_sprites": [
            {
                "arquivo": sprite.arquivo,
                "categoria": sprite.categoria,
                "grupo": sprite.grupo,
                "autor": sprite.autor,
                "fonte": sprite.fonte,
                "licenca": sprite.licenca,
                "especie": sprite.especie,
                "fragmentado": sprite.fragmentado,
                "tamanho_mm": sprite.tamanho_mm,
                "px_por_mm": sprite.px_por_mm,
                "classe_origem": sprite.classe_origem,
                "origem_escala": sprite.origem_escala,
            }
            for sprite in sprites
        ],
        "proporcoes_conjuntos": {"treino": 0.70, "validacao": 0.15, "teste": 0.15},
        "classes_mascara": VALORES_CLASSES,
        "versao_gerador": 2,
    }
    (saida / "configuracao.json").write_text(
        json.dumps(registro_execucao, ensure_ascii=False, sort_keys=True, indent=2)
        + "\n",
        encoding="utf-8",
    )
    return registros


def _criar_faixas_recomposicao(quantidade: int, semente: int) -> list[int]:
    base, resto = divmod(quantidade, len(FAIXAS_COBERTURA_RECOMPOSICAO))
    indices = [
        faixa
        for faixa in range(len(FAIXAS_COBERTURA_RECOMPOSICAO))
        for _ in range(base)
    ]
    indices.extend(range(resto))
    random.Random(semente ^ 0x5EED5EED).shuffle(indices)
    return indices


def classificar_faixa_cobertura_real(percentual: float) -> FaixaCobertura:
    """Classifica a cobertura medida na máscara, com limites do status do produto."""
    return cast(FaixaCobertura, derivar_status(percentual))


def _criar_divisoes_por_faixa(faixas: list[int], semente: int) -> list[str]:
    """Estratifica cada faixa em 70/15/15 com semente independente e estável."""
    divisoes = [""] * len(faixas)
    proporcoes = (0.70, 0.15, 0.15)
    brutos = [len(faixas) * proporcao for proporcao in proporcoes]
    alvos = [math.floor(valor) for valor in brutos]
    ordem_alvos = sorted(
        range(len(proporcoes)),
        key=lambda indice: (-(brutos[indice] - alvos[indice]), indice),
    )
    for indice in ordem_alvos[: len(faixas) - sum(alvos)]:
        alvos[indice] += 1

    totais_por_faixa = [faixas.count(indice) for indice in range(3)]
    faltantes = [
        alvos[indice]
        - sum(
            math.floor(quantidade * proporcoes[indice])
            for quantidade in totais_por_faixa
        )
        for indice in range(len(proporcoes))
    ]
    for indice_faixa in range(len(FAIXAS_COBERTURA_RECOMPOSICAO)):
        indices = [i for i, faixa in enumerate(faixas) if faixa == indice_faixa]
        random.Random(semente ^ (0xA11CE + indice_faixa)).shuffle(indices)
        ideais = [len(indices) * proporcao for proporcao in proporcoes]
        quantidades = [math.floor(valor) for valor in ideais]
        extras = len(indices) - sum(quantidades)
        ordem_extras = sorted(
            range(len(proporcoes)),
            key=lambda indice: (-(ideais[indice] - quantidades[indice]), indice),
        )
        for indice in ordem_extras:
            if extras == 0:
                break
            if faltantes[indice] > 0:
                quantidades[indice] += 1
                faltantes[indice] -= 1
                extras -= 1
        if extras:
            raise RuntimeError("Não foi possível balancear a divisão estratificada.")
        quantidade_treino, quantidade_validacao, _ = quantidades
        for indice in indices[:quantidade_treino]:
            divisoes[indice] = "treino"
        for indice in indices[
            quantidade_treino : quantidade_treino + quantidade_validacao
        ]:
            divisoes[indice] = "validacao"
        for indice in indices[quantidade_treino + quantidade_validacao :]:
            divisoes[indice] = "teste"
    if any(faltantes) or any(not divisao for divisao in divisoes):
        raise RuntimeError("A divisão estratificada não corresponde aos alvos globais.")
    return divisoes


def _sequencia_bases_reais(quantidade: int, proporcao_real: float) -> list[bool]:
    acumulado = 0.0
    sequencia: list[bool] = []
    for _ in range(quantidade):
        acumulado += proporcao_real
        usar_real = acumulado >= 1.0
        sequencia.append(usar_real)
        if usar_real:
            acumulado -= 1.0
    return sequencia


def _descritores_visuais(
    imagem: Image.Image, mascara: Image.Image
) -> dict[str, object]:
    """Mede tom, componentes escuros e aglomeração somente na superfície."""
    import cv2
    import numpy as np

    from training.medicoes_recomposicao import (
        cinza_fixo,
        linhas_longas,
        medir_espalhamento,
    )

    rgb = np.asarray(imagem.convert("RGB"), dtype=np.uint8)
    classes = np.asarray(mascara.convert("L"), dtype=np.uint8)
    placa = (classes == 1) | (classes == 2)
    pixels_placa = int(placa.sum())
    if pixels_placa == 0:
        raise ValueError("Não há área de placa para medir similaridade visual.")
    espalhamento = medir_espalhamento(rgb, classes, True)
    cinza = cinza_fixo(rgb)
    histograma = np.histogram(cinza[placa], bins=32, range=(0, 256), density=False)[
        0
    ].astype(np.float64)
    histograma /= max(1.0, float(histograma.sum()))
    pixels_escuros = (cinza < LIMIAR_PIXEL_ESCURO) & placa
    pixels_escuros_sem_grade = pixels_escuros & ~linhas_longas(pixels_escuros)
    quantidade_escuros, _, estatisticas_escuros, _ = cv2.connectedComponentsWithStats(
        pixels_escuros_sem_grade.astype(np.uint8), connectivity=8
    )
    lados = [
        max(
            int(estatisticas_escuros[indice, cv2.CC_STAT_WIDTH]),
            int(estatisticas_escuros[indice, cv2.CC_STAT_HEIGHT]),
        )
        for indice in range(1, quantidade_escuros)
    ]
    area_pixels_escuros = int(pixels_escuros_sem_grade.sum())
    area_aglomerada_escura = sum(
        int(estatisticas_escuros[indice, cv2.CC_STAT_AREA])
        for indice in range(1, quantidade_escuros)
        if int(estatisticas_escuros[indice, cv2.CC_STAT_AREA])
        > AREA_COMPONENTE_AGLOMERADO
    )
    insetos = (classes == VALORES_CLASSES["placa_coberta"]) & placa
    area_insetos = int(insetos.sum())
    quantidade_componentes, _, estatisticas_insetos, _ = (
        cv2.connectedComponentsWithStats(insetos.astype(np.uint8), connectivity=8)
    )
    area_aglomerada = sum(
        int(estatisticas_insetos[indice, cv2.CC_STAT_AREA])
        for indice in range(1, quantidade_componentes)
        if int(estatisticas_insetos[indice, cv2.CC_STAT_AREA])
        > AREA_COMPONENTE_AGLOMERADO
    )
    return {
        "histograma_cinza": histograma.tolist(),
        "componentes_escuros_maior_lado_px": lados,
        "fracao_pixels_escuros": float(pixels_escuros.sum() / pixels_placa),
        "fracao_aglomerada": area_aglomerada / area_insetos if area_insetos else 0.0,
        "fracao_aglomerada_pixels_escuros": (
            area_aglomerada_escura / area_pixels_escuros if area_pixels_escuros else 0.0
        ),
        "fracao_escura_sem_grade": espalhamento["fracao_escura"],
        "aglomeracao_sem_grade": espalhamento["aglomeracao"],
        "ocupacao_espacial": espalhamento["ocupacao"],
        "percentual_cobertura": 100.0 * area_insetos / pixels_placa,
    }


def _resumir_descritores(
    descritores: list[dict[str, object]],
) -> dict[str, object]:
    import numpy as np

    if not descritores:
        raise ValueError("A avaliação visual precisa de pelo menos uma placa.")
    histogramas = np.asarray(
        [item["histograma_cinza"] for item in descritores], dtype=np.float64
    )
    componentes = [
        int(lado)
        for item in descritores
        for lado in item["componentes_escuros_maior_lado_px"]
    ]
    return {
        "histograma_cinza": histogramas.mean(axis=0).tolist(),
        "componentes_escuros_maior_lado_px": componentes,
        "quantidade_componentes_escuros": len(componentes),
        "fracao_pixels_escuros": float(
            np.mean([item["fracao_pixels_escuros"] for item in descritores])
        ),
        "fracao_aglomerada": float(
            np.mean([item["fracao_aglomerada"] for item in descritores])
        ),
        "fracao_aglomerada_pixels_escuros": float(
            np.mean([item["fracao_aglomerada_pixels_escuros"] for item in descritores])
        ),
        "fracao_escura_sem_grade": float(
            np.mean([item["fracao_escura_sem_grade"] for item in descritores])
        ),
        "aglomeracao_sem_grade": float(
            np.mean([item["aglomeracao_sem_grade"] for item in descritores])
        ),
        "ocupacao_espacial": float(
            np.mean([item["ocupacao_espacial"] for item in descritores])
        ),
        "percentual_cobertura": float(
            np.mean([item["percentual_cobertura"] for item in descritores])
        ),
    }


def _distancia_ks(amostra_a: list[int], amostra_b: list[int]) -> float:
    import numpy as np

    if not amostra_a or not amostra_b:
        return 1.0
    a = np.sort(np.asarray(amostra_a, dtype=np.int64))
    b = np.sort(np.asarray(amostra_b, dtype=np.int64))
    pontos = np.union1d(a, b)
    cdf_a = np.searchsorted(a, pontos, side="right") / len(a)
    cdf_b = np.searchsorted(b, pontos, side="right") / len(b)
    return float(np.max(np.abs(cdf_a - cdf_b)))


def _comparar_descritores_visuais(
    descritores_gerados: list[dict[str, object]],
    descritores_avaliacao: list[dict[str, object]],
) -> dict[str, object]:
    import numpy as np

    gerado = _resumir_descritores(descritores_gerados)
    avaliacao = _resumir_descritores(descritores_avaliacao)
    amostras_cobertura_alta = [
        descritor
        for descritor in descritores_gerados
        if float(descritor["percentual_cobertura"]) >= 50.0
    ]
    gerado_cobertura_alta = (
        _resumir_descritores(amostras_cobertura_alta)
        if amostras_cobertura_alta
        else None
    )
    hist_gerado = np.asarray(gerado["histograma_cinza"], dtype=np.float64)
    hist_avaliacao = np.asarray(avaliacao["histograma_cinza"], dtype=np.float64)
    fracao_escura_gerada = float(gerado["fracao_pixels_escuros"])
    fracao_aglomerada_gerada = (
        float(gerado_cobertura_alta["fracao_aglomerada"])
        if gerado_cobertura_alta is not None
        else None
    )
    return {
        "regiao": "pixels da superfície da placa (classes 1 e 2)",
        "limiar_escuro_cinza": LIMIAR_PIXEL_ESCURO,
        "amostras_geradas": len(descritores_gerados),
        "placas_avaliacao": len(descritores_avaliacao),
        "componentes_escuros_maior_lado_ks": {
            "distancia": _distancia_ks(
                gerado["componentes_escuros_maior_lado_px"],
                avaliacao["componentes_escuros_maior_lado_px"],
            ),
            "componentes_gerados": gerado["quantidade_componentes_escuros"],
            "componentes_avaliacao": avaliacao["quantidade_componentes_escuros"],
            "componentes_referencia_69_placas": COMPONENTES_ESCUROS_REFERENCIA,
        },
        "histograma_cinza_32_faixas_l1_metade": float(
            0.5 * np.abs(hist_gerado - hist_avaliacao).sum()
        ),
        "fracao_pixels_escuros": {
            "gerada": fracao_escura_gerada,
            "referencia_69_placas": 0.0635,
            "avaliacao_media": avaliacao["fracao_pixels_escuros"],
            "diferenca_referencia": fracao_escura_gerada - 0.0635,
        },
        "aglomeracao_classe_2": {
            "criterio": "silhuetas da classe 2 em componentes maiores que 500 px; não comparável diretamente com a referência visual de pixels escuros",
            "gerada_media_todas_as_coberturas": float(gerado["fracao_aglomerada"]),
            "gerada_media_cobertura_50_70": fracao_aglomerada_gerada,
            "amostras_cobertura_50_70": len(amostras_cobertura_alta),
            "avaliacao_media_mascara_rotulada": avaliacao["fracao_aglomerada"],
        },
        "dispersao_visual_sem_grade": {
            "referencia_69_placas_aglomeracao": 0.016,
            "gerada_aglomeracao": gerado["aglomeracao_sem_grade"],
            "avaliacao_14_placas_aglomeracao": avaliacao["aglomeracao_sem_grade"],
            "referencia_ocupacao_tiles_24px": {
                "1-2%": 0.35,
                "2-4%": 0.57,
                "4-8%": 0.88,
            },
            "ocupacao_gerada_media": gerado["ocupacao_espacial"],
            "ocupacao_avaliacao_media": avaliacao["ocupacao_espacial"],
        },
    }


def _avaliar_inpainting(bases: list[BasePlacaReal]) -> dict[str, object]:
    import cv2
    import numpy as np

    alteracoes: list[float] = []
    areas_marcadas: list[float] = []
    for base in bases:
        rgb = np.asarray(base.imagem.convert("RGB"), dtype=np.uint8)
        classes = np.asarray(base.mascara.convert("L"), dtype=np.uint8)
        placa = np.isin(classes, (1, 2))
        alvo = (classes == VALORES_CLASSES["placa_coberta"]).astype(np.uint8) * 255
        if not np.any(alvo):
            continue
        resultado = cv2.inpaint(rgb, alvo, 3, cv2.INPAINT_TELEA)
        mudou = np.any(resultado != rgb, axis=2) & placa
        alteracoes.append(100.0 * float(mudou.sum()) / max(1, int(placa.sum())))
        areas_marcadas.append(
            100.0 * float((alvo > 0).sum()) / max(1, int(placa.sum()))
        )
    return {
        "metodo_testado": "cv2.inpaint TELEA, raio 3, somente nas regiões classe 2",
        "cobertura_marcada_media_percentual": (
            sum(areas_marcadas) / len(areas_marcadas) if areas_marcadas else 0.0
        ),
        "area_alterada_media_percentual": (
            sum(alteracoes) / len(alteracoes) if alteracoes else 0.0
        ),
        "conclusao": (
            "não implementar: as máscaras cobrem 25,6% das anotações originais; "
            "inpainting guiado por classe 2 deixa insetos não rotulados na base, "
            "e não há imagem limpa de referência para validar reconstruções."
        ),
    }


def _sha256_arquivo(caminho: Path) -> str:
    digest = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def _assinatura_recomposicao(
    configuracao: ConfiguracaoDataset,
    diretorio_real: Path,
    placas_composicao: list[Path],
    placas_avaliacao: list[Path],
    fontes_por_conjunto: dict[str, list[Path]],
    recortes_por_conjunto: dict[str, list[RecorteInsetoReal]],
    versoes_bases: dict[str, dict[str, str]],
    pasta_mascaras: Path | None,
    diretorio_recortes: Path | None,
) -> str:
    """Identifica entradas e parâmetros que tornam uma retomada compatível."""
    arquivos_placas = {}
    for placa in sorted((*placas_composicao, *placas_avaliacao)):
        caminho_mascara = (
            pasta_mascaras / f"{placa.stem}.png"
            if pasta_mascaras is not None
            else diretorio_real / "mascaras" / placa.name
        )
        arquivos_placas[placa.stem] = {
            "imagem": _sha256_arquivo(placa),
            "mascara": _sha256_arquivo(caminho_mascara),
        }
    catalogos = {}
    if diretorio_recortes is not None:
        raiz = diretorio_recortes.resolve()
        nomes_fontes = {
            placa.stem for fontes in fontes_por_conjunto.values() for placa in fontes
        }
        for nome in sorted(nomes_fontes):
            catalogo = raiz / "catalogos" / f"{nome}.jsonl"
            catalogos[nome] = _sha256_arquivo(catalogo)
    identidade = {
        "versao": "recomposicao_real_v5_retoma3",
        "parametros": {
            "semente": configuracao.semente,
            "idade_maxima_dias": configuracao.idade_maxima_dias,
            "quantidade": configuracao.quantidade,
            "resolucao": list(configuracao.resolucao),
            "limite_colagens": configuracao.limite_sprites,
            "proporcao_bases_reais": configuracao.proporcao_bases_reais,
            "intensidade_aglomeracao": configuracao.intensidade_aglomeracao,
            "fator_escala_recorte": configuracao.fator_escala_recorte,
            "limite_reuso_recorte": configuracao.limite_reuso_recorte,
            "proporcao_placas_avaliacao": configuracao.proporcao_placas_avaliacao,
            "faixas_alvo": FAIXAS_ALVO_RECOMPOSICAO,
            "compensacao_vies_pp": VIES_TOLERANCIA_ALVO_PP,
        },
        "fontes_por_conjunto": {
            nome: [p.stem for p in fontes]
            for nome, fontes in fontes_por_conjunto.items()
        },
        "mascaras_bases": versoes_bases,
        "manifesto_mascaras_sha256": (
            _sha256_arquivo(pasta_mascaras.parent / "configuracao.json")
            if pasta_mascaras is not None
            else None
        ),
        "arquivos_placas": arquivos_placas,
        "catalogos_recortes_sha256": catalogos,
        "recortes_por_conjunto": {
            nome: [
                {"id": recorte.identificador, "sha256": recorte.sha256_conteudo}
                for recorte in recortes
            ]
            for nome, recortes in recortes_por_conjunto.items()
        },
    }
    serializado = json.dumps(identidade, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(serializado.encode("utf-8")).hexdigest()


def _salvar_checkpoint_recomposicao(
    saida: Path, assinatura: str, amostras_concluidas: int
) -> None:
    caminho = saida / ".progresso.json"
    temporario = caminho.with_suffix(".json.part")
    conteudo = json.dumps(
        {
            "versao": 1,
            "assinatura": assinatura,
            "amostras_concluidas": amostras_concluidas,
        },
        sort_keys=True,
    )
    with temporario.open("w", encoding="utf-8", newline="\n") as arquivo:
        arquivo.write(conteudo + "\n")
        arquivo.flush()
        os.fsync(arquivo.fileno())
    temporario.replace(caminho)


def _escrever_json_atomico(caminho: Path, dados: dict[str, object]) -> None:
    temporario = caminho.with_suffix(caminho.suffix + ".part")
    with temporario.open("w", encoding="utf-8", newline="\n") as arquivo:
        arquivo.write(
            json.dumps(dados, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        )
        arquivo.flush()
        os.fsync(arquivo.fileno())
    temporario.replace(caminho)


def _preparar_retoma_recomposicao(
    saida: Path,
    assinatura: str,
    quantidade: int,
    idade_maxima_dias: float,
    resolucao: tuple[int, int],
    sementes: list[int],
    divisoes: list[str],
    faixas: list[int],
    fontes_por_conjunto: dict[str, list[Path]],
    usos_por_conjunto: dict[str, list[int]],
    recortes_por_conjunto: dict[str, list[RecorteInsetoReal]],
    limite_reuso: int,
) -> tuple[list[dict[str, object]], int]:
    """Valida o checkpoint e recupera uso de recortes sem perder determinismo."""
    permitidos = {
        "imagens",
        "mascaras",
        "metadados.jsonl",
        ".progresso.json",
        ".progresso.json.part",
        "configuracao.json",
        "relatorio_geracao.json",
        "relatorio_auditoria_v5.json",
    }
    if any(caminho.name not in permitidos for caminho in saida.iterdir()):
        raise FileExistsError(f"A saída contém itens fora do gerador: {saida}.")
    caminho_checkpoint = saida / ".progresso.json"
    caminho_metadados = saida / "metadados.jsonl"
    arquivo_checkpoint = caminho_checkpoint.is_file()
    if not arquivo_checkpoint and any(
        caminho.is_file()
        for nome_pasta in ("imagens", "mascaras")
        for caminho in (saida / nome_pasta).iterdir()
    ):
        raise FileExistsError("Imagens sem checkpoint; a saída não será sobrescrita.")
    if (saida / ".progresso.json.part").exists():
        if not arquivo_checkpoint:
            parcial = json.loads((saida / ".progresso.json.part").read_text("utf-8"))
            if (
                parcial.get("versao") != 1
                or parcial.get("assinatura") != assinatura
                or parcial.get("amostras_concluidas") != 0
            ):
                raise FileExistsError("Checkpoint temporário sem estado validado.")
            (saida / ".progresso.json.part").replace(caminho_checkpoint)
            arquivo_checkpoint = True
        else:
            (saida / ".progresso.json.part").unlink()
    if not arquivo_checkpoint and any(
        (saida / nome).exists()
        for nome in ("metadados.jsonl", "configuracao.json", "relatorio_geracao.json")
    ):
        raise FileExistsError("Saída sem checkpoint compatível; não será sobrescrita.")
    estado = (
        json.loads(caminho_checkpoint.read_text("utf-8"))
        if arquivo_checkpoint
        else {"assinatura": assinatura, "amostras_concluidas": 0}
    )
    if estado.get("versao", 1) != 1 or estado.get("assinatura") != assinatura:
        raise ValueError(
            "Os parâmetros ou as fontes diferem do checkpoint desta saída."
        )
    concluidas_checkpoint = int(estado.get("amostras_concluidas", -1))
    if not 0 <= concluidas_checkpoint <= quantidade:
        raise ValueError("O checkpoint tem uma contagem de amostras inválida.")

    registros: list[dict[str, object]] = []
    linhas = []
    if caminho_metadados.is_file():
        conteudo = caminho_metadados.read_bytes()
        linhas = conteudo.splitlines(keepends=True)
        if linhas and not linhas[-1].endswith((b"\n", b"\r")):
            if not arquivo_checkpoint:
                raise ValueError("Metadados incompletos sem checkpoint de retomada.")
            tamanho_valido = sum(len(linha) for linha in linhas[:-1])
            with caminho_metadados.open("r+b") as arquivo:
                arquivo.truncate(tamanho_valido)
            linhas = linhas[:-1]
        for linha in linhas:
            if not linha.strip():
                continue
            registros.append(json.loads(linha))
    if (
        len(registros) < concluidas_checkpoint
        or len(registros) > concluidas_checkpoint + 1
    ):
        raise ValueError("Contagem do manifesto diverge do checkpoint.")
    if len(registros) > quantidade:
        raise ValueError("O manifesto contém mais amostras que o solicitado.")

    recortes_por_id = {
        recorte.identificador: (conjunto, indice)
        for conjunto, recortes in recortes_por_conjunto.items()
        for indice, recorte in enumerate(recortes)
    }
    for indice, registro in enumerate(registros):
        esperado_id = f"amostra_{indice + 1:06d}"
        if (
            registro.get("id") != esperado_id
            or registro.get("semente") != sementes[indice]
            or registro.get("conjunto") != divisoes[indice]
            or registro.get("faixa_cobertura_alvo")
            != FAIXAS_COBERTURA_RECOMPOSICAO[faixas[indice]][0]
        ):
            raise ValueError(f"Metadados divergentes na amostra {esperado_id}.")
        _, minimo, maximo = FAIXAS_ALVO_RECOMPOSICAO[faixas[indice]]
        alvo_esperado = random.Random(sementes[indice] ^ 0xC0B3A7).uniform(
            minimo, maximo
        )
        idade_esperada = random.Random(sementes[indice] ^ 0xA61DADE).uniform(
            0.0, idade_maxima_dias
        )
        if not math.isclose(
            float(registro["percentual_cobertura_alvo"]),
            alvo_esperado,
            rel_tol=0.0,
            abs_tol=1e-12,
        ) or not math.isclose(
            float(registro["idade_simulada_dias"]),
            idade_esperada,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError(f"Alvo ou idade divergente em {esperado_id}.")
        if registro.get("faixa_cobertura_real") != classificar_faixa_cobertura_real(
            float(registro["percentual_cobertura_real"])
        ):
            raise ValueError(f"Faixa real divergente em {esperado_id}.")
        conjunto = str(registro["conjunto"])
        fontes_permitidas = {p.stem for p in fontes_por_conjunto[conjunto]}
        if not set(registro.get("placas_origem_recortes", [])) <= fontes_permitidas or (
            registro.get("placa_base_id") is not None
            and registro["placa_base_id"] not in fontes_permitidas
        ):
            raise ValueError(f"Fonte cruzada entre conjuntos em {esperado_id}.")
        contagens_amostra: Counter[str] = Counter(
            str(valor) for valor in registro.get("recortes_coco_ids_usados", [])
        )
        if max(contagens_amostra.values(), default=0) > limite_reuso:
            raise ValueError(f"Reuso acima do limite em {esperado_id}.")
        for identificador_recorte, ocorrencias in contagens_amostra.items():
            encontrado = recortes_por_id.get(identificador_recorte)
            if encontrado is None or encontrado[0] != conjunto:
                raise ValueError(
                    f"Recorte incompatível com o conjunto em {esperado_id}."
                )
            usos_por_conjunto[conjunto][encontrado[1]] += ocorrencias
        for pasta in (saida / "imagens", saida / "mascaras"):
            artefato = pasta / f"{esperado_id}.png"
            if not artefato.is_file() or artefato.stat().st_size == 0:
                raise ValueError(f"Artefato ausente ou vazio: {artefato}.")
            with Image.open(artefato) as imagem:
                imagem.verify()
                if imagem.size != resolucao:
                    raise ValueError(f"Resolução divergente no artefato {artefato}.")
    if len(registros) == concluidas_checkpoint + 1:
        _salvar_checkpoint_recomposicao(saida, assinatura, len(registros))

    proxima = len(registros) + 1
    for nome_pasta in ("imagens", "mascaras"):
        pasta = saida / nome_pasta
        inesperados = []
        for caminho in pasta.iterdir():
            if not caminho.is_file() or not caminho.name.endswith(".png"):
                if (
                    caminho.name.endswith(".png.part")
                    and caminho.stem == f"amostra_{proxima:06d}.png"
                ):
                    caminho.unlink()
                    continue
                inesperados.append(caminho.name)
                continue
            try:
                numero = int(caminho.stem.removeprefix("amostra_"))
            except ValueError:
                inesperados.append(caminho.name)
                continue
            if numero > proxima or numero < 1:
                inesperados.append(caminho.name)
        if inesperados:
            raise FileExistsError(
                f"Arquivos inesperados em {pasta}: {', '.join(inesperados[:5])}."
            )
    for nome in ("configuracao.json", "relatorio_geracao.json"):
        if (saida / nome).exists() and len(registros) != quantidade:
            raise ValueError("Relatório final encontrado em execução incompleta.")
    return registros, len(registros)


def _gerar_dataset_recomposicao_real(
    configuracao: ConfiguracaoDataset,
    parar_apos: int | None = None,
) -> list[dict[str, object]]:
    """Gera amostras sem usar recortes ou bases de placas reservadas à avaliação."""
    diretorio_real = configuracao.diretorio_placas_reais
    if diretorio_real is None:
        raise ValueError("O diretório das placas reais é obrigatório nesta modalidade.")
    diretorio_real = diretorio_real.resolve()
    if not diretorio_real.is_dir():
        raise FileNotFoundError(f"Conjunto de placas reais ausente: {diretorio_real}.")
    if parar_apos is not None and not 0 < parar_apos < configuracao.quantidade:
        raise ValueError("parar_apos deve ficar entre 1 e a quantidade total.")
    saida = configuracao.diretorio_saida.resolve()

    # A separação é definida por identificador antes da carga de imagens ou máscaras.
    placas_composicao, placas_avaliacao = _dividir_placas_reais(
        diretorio_real,
        configuracao.semente,
        configuracao.proporcao_placas_avaliacao,
    )
    manifest = None
    pasta_mascaras_bases = None
    versoes_bases: dict[str, dict[str, str]] = {}
    if configuracao.diretorio_mascaras_bases is not None:
        pasta_mascaras_bases = configuracao.diretorio_mascaras_bases.resolve()
        manifest = json.loads(
            (pasta_mascaras_bases.parent / "configuracao.json").read_text("utf-8")
        )
        from training.estruturas_bases import validar_aceite_bases

        validar_aceite_bases(manifest)
        ids_bases_elegiveis = set(manifest["bases_elegiveis"])
    else:
        ids_bases_elegiveis = {Path(nome).stem for nome in NOMES_BASES_REAIS}
    fontes_por_conjunto = _particionar_fontes(
        placas_composicao, configuracao.semente, ids_bases_elegiveis
    )
    ids_composicao = {caminho.stem for caminho in placas_composicao}
    if configuracao.diretorio_recortes_reais is not None:
        recortes, componentes_por_placa, aceitos_por_placa = _carregar_recortes_coco(
            configuracao.diretorio_recortes_reais, ids_composicao
        )
    else:
        bases_composicao = tuple(
            _carregar_base_real(caminho, diretorio_real, configuracao.resolucao)
            for caminho in placas_composicao
        )
        recortes, componentes_por_placa, aceitos_por_placa = _extrair_recortes_reais(
            bases_composicao
        )
    bases_reais = []
    for caminho in placas_composicao:
        if caminho.stem not in ids_bases_elegiveis:
            continue
        if pasta_mascaras_bases is not None:
            base = _carregar_base_real(
                caminho,
                diretorio_real,
                configuracao.resolucao,
                pasta_mascaras_bases,
            )
        else:
            base = _carregar_base_real(caminho, diretorio_real, configuracao.resolucao)
        bases_reais.append(base)
    if not bases_reais:
        raise ValueError("Nenhuma base real elegível está disponível para composição.")

    import numpy as np

    from training.medicoes_recomposicao import medir_espalhamento

    aglomeracao_bases_reais = {
        base.identificador: medir_espalhamento(
            np.asarray(base.imagem.convert("RGB")),
            np.asarray(base.mascara.convert("L")),
            sem_grade=True,
        )["aglomeracao"]
        for base in bases_reais
    }

    if pasta_mascaras_bases is not None:
        for base in bases_reais:
            caminho = pasta_mascaras_bases / f"{base.identificador}.png"
            registro_revisao = next(
                (p for p in manifest["placas"] if p["placa"] == base.identificador),
                None,
            )
            resumo = hashlib.sha256(caminho.read_bytes()).hexdigest()
            if (
                registro_revisao is None
                or registro_revisao.get("sha256_complementar") != resumo
            ):
                raise ValueError(
                    f"Máscara complementar alterada ou sem revisão: {base.identificador}."
                )
            versoes_bases[base.identificador] = {
                "versao": str(manifest["versao"]),
                "sha256": resumo,
            }
    else:
        versoes_bases = {
            base.identificador: {"versao": "mascara_fonte_teste_real_ums"}
            for base in bases_reais
        }
    bases_por_conjunto: dict[str, list[BasePlacaReal]] = {}
    recortes_por_conjunto: dict[str, list[RecorteInsetoReal]] = {}
    for conjunto, fontes in fontes_por_conjunto.items():
        ids = {p.stem for p in fontes}
        bases_por_conjunto[conjunto] = [
            b for b in bases_reais if b.identificador in ids
        ]
        recortes_por_conjunto[conjunto] = [r for r in recortes if r.placa_origem in ids]
        if not recortes_por_conjunto[conjunto]:
            raise ValueError(
                f"O conjunto {conjunto} precisa de recortes das próprias placas."
            )

    pasta_imagens = saida / "imagens"
    pasta_mascaras_saida = saida / "mascaras"
    pasta_imagens.mkdir(parents=True, exist_ok=True)
    pasta_mascaras_saida.mkdir(parents=True, exist_ok=True)
    rng_global = random.Random(configuracao.semente)
    sementes = [rng_global.getrandbits(64) for _ in range(configuracao.quantidade)]
    faixas = _criar_faixas_recomposicao(configuracao.quantidade, configuracao.semente)
    divisoes = _criar_divisoes_por_faixa(faixas, configuracao.semente)
    sequencia_bases = _sequencia_bases_reais(
        configuracao.quantidade, configuracao.proporcao_bases_reais
    )
    for indice, conjunto in enumerate(divisoes):
        if not bases_por_conjunto[conjunto]:
            sequencia_bases[indice] = False
    usos_por_conjunto = {
        nome: [0] * len(pool) for nome, pool in recortes_por_conjunto.items()
    }
    caminho_metadados = saida / "metadados.jsonl"
    assinatura_geracao = _assinatura_recomposicao(
        configuracao,
        diretorio_real,
        placas_composicao,
        placas_avaliacao,
        fontes_por_conjunto,
        recortes_por_conjunto,
        versoes_bases,
        pasta_mascaras_bases,
        configuracao.diretorio_recortes_reais,
    )
    registros, inicio_geracao = _preparar_retoma_recomposicao(
        saida,
        assinatura_geracao,
        configuracao.quantidade,
        configuracao.idade_maxima_dias,
        configuracao.resolucao,
        sementes,
        divisoes,
        faixas,
        fontes_por_conjunto,
        usos_por_conjunto,
        recortes_por_conjunto,
        configuracao.limite_reuso_recorte,
    )
    if (
        len(registros) == configuracao.quantidade
        and (saida / "configuracao.json").is_file()
        and (saida / "relatorio_geracao.json").is_file()
    ):
        for nome in ("configuracao.json", "relatorio_geracao.json"):
            final = json.loads((saida / nome).read_text("utf-8"))
            if final.get("assinatura_execucao") != assinatura_geracao:
                raise ValueError(f"{nome} não corresponde ao checkpoint atual.")
        return registros
    _salvar_checkpoint_recomposicao(saida, assinatura_geracao, len(registros))
    modo_metadados = "a" if inicio_geracao else "w"
    with caminho_metadados.open(
        modo_metadados, encoding="utf-8", newline="\n"
    ) as arquivo:
        limite_execucao = min(len(sementes), parar_apos or len(sementes))
        for indice in range(inicio_geracao, limite_execucao):
            semente_amostra = sementes[indice]
            conjunto = divisoes[indice]
            recortes_amostra = recortes_por_conjunto[conjunto]
            usos_globais = usos_por_conjunto[conjunto]
            rng = random.Random(semente_amostra)
            rng_cobertura = random.Random(semente_amostra ^ 0xC0B3A7)
            rng_idade = random.Random(semente_amostra ^ 0xA61DADE)
            faixa, _, _ = FAIXAS_COBERTURA_RECOMPOSICAO[faixas[indice]]
            _, minimo, maximo = FAIXAS_ALVO_RECOMPOSICAO[faixas[indice]]
            percentual_alvo = rng_cobertura.uniform(minimo, maximo)
            idade_simulada = rng_idade.uniform(0.0, configuracao.idade_maxima_dias)
            usar_base_real = sequencia_bases[indice]
            if usar_base_real:
                candidatas_base = _bases_compativeis_com_alvo(
                    bases_por_conjunto[conjunto],
                    percentual_alvo,
                    aglomeracao_bases_reais,
                )
                base = rng.choice(candidatas_base)
                imagem_base, mascara_base = base.imagem.copy(), base.mascara.copy()
                identificador_base: str | None = base.identificador
                tipo_base = "real_ums"
            else:
                imagem_base, mascara_base = _criar_base_sintetica(
                    configuracao.resolucao, rng
                )
                identificador_base = None
                tipo_base = "sintetica_stickfly_k45"
            distratores: list[str] = []
            if not usar_base_real:
                distratores = _selecionar_distratores(rng) or ["poeira"]
                import numpy as np

                ys, xs = np.nonzero(np.asarray(mascara_base) == 1)
                rgba = imagem_base.convert("RGBA")
                _desenhar_distratores(
                    rgba,
                    (
                        int(xs.min()),
                        int(ys.min()),
                        int(xs.max()) + 1,
                        int(ys.max()) + 1,
                    ),
                    distratores,
                    rng,
                )
                imagem_base = rgba.convert("RGB")
            imagem, mascara, composicao = _compor_recortes_reais(
                imagem_base,
                mascara_base,
                recortes_amostra,
                percentual_alvo,
                rng,
                configuracao.limite_sprites,
                configuracao.limite_reuso_recorte,
                configuracao.intensidade_aglomeracao,
                usos_globais,
                configuracao.fator_escala_recorte,
            )
            for indice_recorte in composicao.pop("_indices_recortes_usados"):
                usos_globais[int(indice_recorte)] += 1
            recortes_coco_ids_usados = composicao["recortes_coco_ids_usados"]
            identificador = f"amostra_{indice + 1:06d}"
            caminho_imagem = pasta_imagens / f"{identificador}.png"
            caminho_mascara = pasta_mascaras_saida / f"{identificador}.png"
            temporario_imagem = caminho_imagem.with_suffix(".png.part")
            temporario_mascara = caminho_mascara.with_suffix(".png.part")
            imagem.save(temporario_imagem, format="PNG")
            mascara.save(temporario_mascara, format="PNG")
            temporario_imagem.replace(caminho_imagem)
            temporario_mascara.replace(caminho_mascara)
            placas_origem = composicao["placas_origem_recortes"]
            ids_avaliacao = {caminho.stem for caminho in placas_avaliacao}
            if ids_avaliacao.intersection(placas_origem):
                raise RuntimeError(
                    "Um recorte de placa de avaliação entrou na geração."
                )
            fontes_permitidas = {p.stem for p in fontes_por_conjunto[conjunto]}
            if not set(placas_origem) <= fontes_permitidas or (
                identificador_base is not None
                and identificador_base not in fontes_permitidas
            ):
                raise RuntimeError("Uma fonte de outro conjunto entrou na geração.")
            registro: dict[str, object] = {
                "id": identificador,
                "semente": semente_amostra,
                "conjunto": divisoes[indice],
                "faixa_cobertura_alvo": faixa,
                "faixa_cobertura_real": classificar_faixa_cobertura_real(
                    float(composicao["percentual_cobertura_real"])
                ),
                "percentual_cobertura_alvo": percentual_alvo,
                "percentual_cobertura_real": composicao["percentual_cobertura_real"],
                "alvo_atingido": abs(
                    float(composicao["percentual_cobertura_real"]) - percentual_alvo
                )
                <= TOLERANCIA_RECOMPOSICAO_PP + 1e-9,
                "idade_simulada_dias": idade_simulada,
                "n_sprites": composicao["n_recortes"],
                "n_recortes": composicao["n_recortes"],
                "distratores_presentes": distratores,
                "dominante_cor": "preservada_da_fonte",
                "mascara_classes": {**VALORES_CLASSES, "ignorada": 255},
                "pesos_grupo": {},
                "origem_base": tipo_base,
                "placa_base_id": identificador_base,
                "conjunto_placa_base": conjunto if identificador_base else None,
                "mascara_base_versao": versoes_bases[identificador_base]
                if identificador_base
                else {"versao": "sintetica_exata_v1"},
                "cobertura_herdada_base_percentual": composicao[
                    "cobertura_herdada_base_percentual"
                ],
                "cobertura_adicionada_percentual": composicao[
                    "cobertura_adicionada_percentual"
                ],
                "fracao_aglomerada": composicao["fracao_aglomerada"],
                "maior_reuso_recorte_na_amostra": composicao[
                    "maior_reuso_recorte_na_amostra"
                ],
                "placas_origem_recortes": placas_origem,
                "conjunto_placas_origem_recortes": {
                    origem: conjunto for origem in placas_origem
                },
                "recortes_coco_ids_usados": recortes_coco_ids_usados,
                "taxons_recortes_usados": composicao["taxons_recortes_usados"],
            }
            registros.append(registro)
            arquivo.write(
                json.dumps(
                    registro, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                )
                + "\n"
            )
            arquivo.flush()
            os.fsync(arquivo.fileno())
            _salvar_checkpoint_recomposicao(saida, assinatura_geracao, len(registros))
            if len(registros) % 50 == 0 or len(registros) == configuracao.quantidade:
                percentual = 100.0 * len(registros) / configuracao.quantidade
                print(
                    f"Progresso: {len(registros)}/{configuracao.quantidade} "
                    f"amostras ({percentual:.1f}%)",
                    flush=True,
                )

    if parar_apos is not None and len(registros) < configuracao.quantidade:
        return registros

    quantidade_descritores = min(configuracao.quantidade, AMOSTRAS_DESCRITORES_VISUAIS)
    indices_descritores = {
        round(
            indice * (configuracao.quantidade - 1) / max(1, quantidade_descritores - 1)
        )
        for indice in range(quantidade_descritores)
    }
    altos = [
        i
        for i, r in enumerate(registros)
        if float(r["percentual_cobertura_real"]) >= 50
    ]
    indices_descritores.update(altos[:30])
    descritores_gerados: list[dict[str, object]] = []
    for indice in sorted(indices_descritores):
        identificador = str(registros[indice]["id"])
        with Image.open(pasta_imagens / f"{identificador}.png") as origem:
            imagem = origem.convert("RGB")
        with Image.open(pasta_mascaras_saida / f"{identificador}.png") as origem:
            mascara = origem.convert("L")
        descritores_gerados.append(_descritores_visuais(imagem, mascara))

    bases_avaliacao = [
        _carregar_base_real(
            caminho,
            diretorio_real,
            configuracao.resolucao,
            pasta_mascaras_bases,
        )
        if pasta_mascaras_bases is not None
        else _carregar_base_real(caminho, diretorio_real, configuracao.resolucao)
        for caminho in placas_avaliacao
    ]
    descritores_avaliacao = [
        _descritores_visuais(base.imagem, base.mascara) for base in bases_avaliacao
    ]
    comparacao_visual = _comparar_descritores_visuais(
        descritores_gerados, descritores_avaliacao
    )
    avaliacao_inpainting = _avaliar_inpainting(bases_reais)
    alvo_alto = [
        float(registro["fracao_aglomerada"])
        for registro in registros
        if float(registro["percentual_cobertura_alvo"]) >= 50.0
    ]
    maximo_reuso = max(
        (u for usos in usos_por_conjunto.values() for u in usos), default=0
    )
    configuracao_saida = {
        "assinatura_execucao": assinatura_geracao,
        "semente_global": configuracao.semente,
        "semente_divisao_placas": configuracao.semente,
        "quantidade": configuracao.quantidade,
        "idade_maxima_dias": configuracao.idade_maxima_dias,
        "resolucao": list(configuracao.resolucao),
        "fonte_placas_reais": str(diretorio_real),
        "faixas_cobertura_alvo": {
            nome: [minimo, maximo] for nome, minimo, maximo in FAIXAS_ALVO_RECOMPOSICAO
        },
        "faixas_cobertura_real": {
            nome: [minimo, maximo]
            for nome, minimo, maximo in FAIXAS_COBERTURA_RECOMPOSICAO
        },
        "compensacao_vies_tolerancia_alvo_pp": VIES_TOLERANCIA_ALVO_PP,
        "classificacao_faixa": "percentual_real_da_mascara_v1",
        "proporcao_bases_reais": configuracao.proporcao_bases_reais,
        "intensidade_aglomeracao": configuracao.intensidade_aglomeracao,
        "fator_escala_recorte": configuracao.fator_escala_recorte,
        "lado_maximo_recorte_disperso_px": LADO_MAXIMO_RECORTE_DISPERSO,
        "raio_foco_fracao_placa": {
            "largura": FRACAO_RAIO_FOCO_LARGURA,
            "altura": FRACAO_RAIO_FOCO_ALTURA,
        },
        "numero_focos_por_alvo": {
            "minimo": NUMERO_MINIMO_FOCOS,
            "maximo": NUMERO_MAXIMO_FOCOS,
            "regra": "clamp(round(4 + percentual_alvo / 25))",
        },
        "margem_dispersao_fracao_erosao": FRACAO_MARGEM_DISPERSAO,
        "espacamento_recortes_dispersos_divisor_lado": DIVISOR_ESPACAMENTO_DISPERSO,
        "eficiencia_estimada_area_aglomerada": EFICIENCIA_AREA_AGLOMERADA,
        "eficiencia_estimada_area_dispersada": EFICIENCIA_AREA_DISPERSA,
        "limite_reuso_recorte": configuracao.limite_reuso_recorte,
        "limite_colagens": configuracao.limite_sprites,
        "proporcao_placas_avaliacao": configuracao.proporcao_placas_avaliacao,
        "erosao_adesiva_px_em_768x576": EROSAO_PLACA_PX,
        "limiar_dark_cinza": LIMIAR_PIXEL_ESCURO,
        "classes_mascara": {**VALORES_CLASSES, "ignorada": 255},
        "versao_gerador": 5,
        "versao_calibracao": "colagens_300_900_v1",
        "mascaras_bases": versoes_bases,
        "fontes_por_conjunto": {
            nome: [p.stem for p in fontes]
            for nome, fontes in fontes_por_conjunto.items()
        },
        "recortes_por_conjunto": {
            nome: [r.identificador for r in recortes_por_conjunto[nome]]
            for nome in recortes_por_conjunto
        },
    }
    relatorio = {
        "assinatura_execucao": assinatura_geracao,
        "semente_global": configuracao.semente,
        "separacao_placas": {
            "semente": configuracao.semente,
            "total": len(placas_composicao) + len(placas_avaliacao),
            "composicao": [caminho.stem for caminho in placas_composicao],
            "avaliacao": [caminho.stem for caminho in placas_avaliacao],
            "nenhuma_placa_avaliacao_usada_na_geracao": True,
        },
        "extracao_recortes": {
            "area_minima_px": AREA_MINIMA_RECORTE_REAL,
            "proporcao_maxima": PROPORCAO_MAXIMA_RECORTE_REAL,
            "componentes_encontrados_em_placas_de_composicao": sum(
                componentes_por_placa.values()
            ),
            "recortes_aceitos": len(recortes),
            "placas_com_recortes": sum(
                valor > 0 for valor in aceitos_por_placa.values()
            ),
            "maior_lado_percentis_px": _percentis_tamanho_recortes(recortes),
            "recortes_por_placa": aceitos_por_placa,
        },
        "bases_reais": [base.identificador for base in bases_reais],
        "fontes_por_conjunto": {
            nome: {
                "placas_origem": [p.stem for p in fontes],
                "bases_reais": [b.identificador for b in bases_por_conjunto[nome]],
                "recortes": len(recortes_por_conjunto[nome]),
            }
            for nome, fontes in fontes_por_conjunto.items()
        },
        "bases_elegiveis_por_conjunto": {
            nome: [base.identificador for base in bases_por_conjunto[nome]]
            for nome in bases_por_conjunto
        },
        "bases_elegiveis": sorted(base.identificador for base in bases_reais),
        "aglomeracao_por_base_real": aglomeracao_bases_reais,
        "limite_aglomeracao_base_para_alvos_abaixo_de_20": (
            LIMITE_AGLOMERACAO_BASE_BAIXA_COBERTURA
        ),
        "quantidade_bases_elegiveis_por_conjunto": {
            nome: len(bases_por_conjunto[nome]) for nome in bases_por_conjunto
        },
        "avaliacao_real_rotulo_incompleto": True,
        "diversidade_fundos": (
            f"{len(bases_reais)} bases elegíveis distribuídas como "
            + "/".join(
                str(len(bases_por_conjunto[nome]))
                for nome in ("treino", "validacao", "teste")
            )
            + " (treino/validação/teste). A meta é três bases por conjunto; "
            "uma alternativa futura é revisar e anotar novas placas-base "
            "independentes."
        ),
        "separacao_por_faixa": {
            faixa: {
                conjunto: sum(
                    r["faixa_cobertura_alvo"] == faixa and r["conjunto"] == conjunto
                    for r in registros
                )
                for conjunto in ("treino", "validacao", "teste")
            }
            for faixa, _, _ in FAIXAS_COBERTURA_RECOMPOSICAO
        },
        "separacao_por_faixa_real": {
            faixa: {
                conjunto: sum(
                    r["faixa_cobertura_real"] == faixa and r["conjunto"] == conjunto
                    for r in registros
                )
                for conjunto in ("treino", "validacao", "teste")
            }
            for faixa, _, _ in FAIXAS_COBERTURA_RECOMPOSICAO
        },
        "alvos_atingidos_por_faixa": {
            faixa: {
                "amostras": sum(r["faixa_cobertura_alvo"] == faixa for r in registros),
                "atingidos": sum(
                    r["faixa_cobertura_alvo"] == faixa and r["alvo_atingido"]
                    for r in registros
                ),
                "taxa": (
                    sum(
                        r["faixa_cobertura_alvo"] == faixa and r["alvo_atingido"]
                        for r in registros
                    )
                    / max(1, sum(r["faixa_cobertura_alvo"] == faixa for r in registros))
                ),
            }
            for faixa, _, _ in FAIXAS_COBERTURA_RECOMPOSICAO
        },
        "distratores": dict(
            Counter(d for r in registros for d in r["distratores_presentes"])
        ),
        "amostras": configuracao.quantidade,
        "bases_reais_usadas": sum(sequencia_bases),
        "bases_sinteticas_usadas": configuracao.quantidade - sum(sequencia_bases),
        "maximo_reuso_recorte_no_conjunto": maximo_reuso,
        "limite_reuso_recorte_por_amostra": configuracao.limite_reuso_recorte,
        "fracao_aglomerada_media_alvos_acima_50": (
            sum(alvo_alto) / len(alvo_alto) if alvo_alto else None
        ),
        "descritores_visuais": comparacao_visual,
        "avaliacao_inpainting": avaliacao_inpainting,
    }
    _escrever_json_atomico(saida / "configuracao.json", configuracao_saida)
    _escrever_json_atomico(saida / "relatorio_geracao.json", relatorio)
    return registros


def _percentis_tamanho_recortes(
    recortes: list[RecorteInsetoReal],
) -> dict[str, float]:
    import numpy as np

    lados = [max(recorte.imagem.size) for recorte in recortes]
    return {
        f"p{percentil}": float(np.percentile(lados, percentil))
        for percentil in (10, 50, 90)
    }


def _texto_obrigatorio(registro: dict[str, object], campo: str, indice: int) -> str:
    valor = registro.get(campo)
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"O campo '{campo}' do sprite {indice} é obrigatório.")
    return valor.strip()


def _numero_positivo_opcional(
    registro: dict[str, object], campo: str, indice: int
) -> float | None:
    valor = registro.get(campo)
    if valor is None:
        return None
    if (
        isinstance(valor, bool)
        or not isinstance(valor, (int, float))
        or not math.isfinite(valor)
        or valor <= 0
    ):
        raise ValueError(
            f"'{campo}' do sprite {indice} precisa ser um número positivo."
        )
    return float(valor)


def _calcular_caixa_placa(
    largura: int,
    altura: int,
    rng: random.Random,
    px_por_mm: float,
) -> tuple[tuple[int, int, int, int], int]:
    margem_x = max(2, int(largura * 0.02))
    margem_y = max(2, int(altura * 0.035))
    largura_placa = min(
        round(DIMENSOES_REFIL_MM[0] * px_por_mm * rng.uniform(0.95, 1.0)),
        largura - margem_x * 2,
        round(altura * 0.62 * DIMENSOES_REFIL_MM[0] / DIMENSOES_REFIL_MM[1]),
    )
    altura_placa = round(largura_placa * DIMENSOES_REFIL_MM[1] / DIMENSOES_REFIL_MM[0])
    margem_moldura = max(2, int(altura_placa * rng.uniform(0.035, 0.065)))
    largura_externa = largura_placa + margem_moldura * 2
    altura_externa = altura_placa + margem_moldura * 2
    max_largura_externa = largura - margem_x * 2
    if largura_externa > max_largura_externa:
        largura_placa = max_largura_externa - margem_moldura * 2
        altura_placa = round(
            largura_placa * DIMENSOES_REFIL_MM[1] / DIMENSOES_REFIL_MM[0]
        )
        largura_externa = largura_placa + margem_moldura * 2
        altura_externa = altura_placa + margem_moldura * 2
    max_altura_externa = altura - margem_y * 2
    if altura_externa > max_altura_externa:
        altura_placa = max_altura_externa - margem_moldura * 2
        largura_placa = round(
            altura_placa * DIMENSOES_REFIL_MM[0] / DIMENSOES_REFIL_MM[1]
        )
        largura_externa = largura_placa + margem_moldura * 2
        altura_externa = altura_placa + margem_moldura * 2
    externo_x = rng.randint(
        margem_x, max(margem_x, largura - largura_externa - margem_x)
    )
    externo_y = rng.randint(margem_y, max(margem_y, altura - altura_externa - margem_y))
    return (
        (
            externo_x + margem_moldura,
            externo_y + margem_moldura,
            externo_x + margem_moldura + largura_placa,
            externo_y + margem_moldura + altura_placa,
        ),
        margem_moldura,
    )


def _criar_cena(
    largura: int,
    altura: int,
    caixa_placa: tuple[int, int, int, int],
    margem_moldura: int,
    idade_relativa: float,
    rng: random.Random,
) -> tuple[Image.Image, Image.Image, str, tuple[int, int, int]]:
    largura_placa = caixa_placa[2] - caixa_placa[0]
    altura_placa = caixa_placa[3] - caixa_placa[1]
    cor_nova = (247.0, 237.0, 194.0)
    cor_envelhecida = (211.0, 177.0, 111.0)
    cor_base = [
        nova * (1 - idade_relativa) + velha * idade_relativa
        for nova, velha in zip(cor_nova, cor_envelhecida, strict=True)
    ]
    cor_base[0] += rng.uniform(-5, 5)
    cor_base[1] += rng.uniform(-7, 7)
    cor_base[2] += rng.uniform(-8, 8)
    dominante_rgb = (
        max(0, min(255, round(cor_base[0]))),
        max(0, min(255, round(min(cor_base[1], cor_base[0] - 5)))),
        max(0, min(255, round(min(cor_base[2], cor_base[1] - 7)))),
    )
    nome_dominante = "creme_envelhecido" if idade_relativa > 0.55 else "creme_amarelado"

    cena = Image.new("RGBA", (largura, altura), (211, 212, 205, 255))
    caixa_moldura = (
        caixa_placa[0] - margem_moldura,
        caixa_placa[1] - margem_moldura,
        caixa_placa[2] + margem_moldura,
        caixa_placa[3] + margem_moldura,
    )
    desenho = ImageDraw.Draw(cena)
    deslocamento_sombra = max(1, round(margem_moldura * 0.35))
    camada_sombra = Image.new("RGBA", cena.size, (0, 0, 0, 0))
    ImageDraw.Draw(camada_sombra).rectangle(
        (
            caixa_moldura[0] + deslocamento_sombra,
            caixa_moldura[1] + deslocamento_sombra,
            caixa_moldura[2] - 1 + deslocamento_sombra,
            caixa_moldura[3] - 1 + deslocamento_sombra,
        ),
        fill=(31, 35, 31, rng.randint(30, 64)),
    )
    cena.alpha_composite(
        camada_sombra.filter(ImageFilter.GaussianBlur(max(1, margem_moldura * 0.55)))
    )
    desenho = ImageDraw.Draw(cena)
    desenho.rounded_rectangle(
        (
            caixa_moldura[0],
            caixa_moldura[1],
            caixa_moldura[2] - 1,
            caixa_moldura[3] - 1,
        ),
        radius=max(2, margem_moldura // 4),
        fill=(42, 49, 45, 255),
        outline=(28, 35, 32, 255),
        width=max(1, margem_moldura // 16),
    )
    recuo_moldura = max(1, margem_moldura // 6)
    desenho.rectangle(
        (
            caixa_moldura[0] + recuo_moldura,
            caixa_moldura[1] + recuo_moldura,
            caixa_moldura[2] - recuo_moldura - 1,
            caixa_moldura[3] - recuo_moldura - 1,
        ),
        fill=(224, 221, 204, 255),
        outline=(179, 178, 160, 255),
        width=max(1, margem_moldura // 20),
    )
    caixa_placa_inclusiva = (
        caixa_placa[0],
        caixa_placa[1],
        caixa_placa[2] - 1,
        caixa_placa[3] - 1,
    )
    camada_placa = Image.new(
        "RGBA", (largura_placa, altura_placa), (*dominante_rgb, 255)
    )
    textura = Image.new("RGBA", camada_placa.size, (0, 0, 0, 0))
    desenho_textura = ImageDraw.Draw(textura)
    for _ in range(rng.randint(8, 18)):
        x = rng.randrange(largura_placa)
        y = rng.randrange(altura_placa)
        raio_x = rng.randint(max(2, largura_placa // 100), max(3, largura_placa // 26))
        raio_y = rng.randint(max(2, altura_placa // 80), max(3, altura_placa // 24))
        desenho_textura.ellipse(
            (x - raio_x, y - raio_y, x + raio_x, y + raio_y),
            fill=(151, 115, 53, rng.randint(3, 13)),
        )
    for _ in range(max(24, largura_placa // 8)):
        x = rng.randrange(largura_placa)
        y = rng.randrange(altura_placa)
        comprimento = rng.randint(2, max(3, largura_placa // 18))
        desenho_textura.line(
            (x, y, min(largura_placa - 1, x + comprimento), y + rng.choice((-1, 0, 1))),
            fill=(119, 107, 76, rng.randint(4, 16)),
            width=1,
        )
    for _ in range(max(40, (largura_placa * altura_placa) // 1400)):
        x = rng.randrange(largura_placa)
        y = rng.randrange(altura_placa)
        tom = rng.randint(128, 200)
        desenho_textura.point((x, y), fill=(tom, max(0, tom - 20), max(0, tom - 54), 6))
    camada_placa.alpha_composite(textura.filter(ImageFilter.GaussianBlur(radius=0.4)))
    cena.alpha_composite(camada_placa, dest=(caixa_placa[0], caixa_placa[1]))

    mascara = Image.new("L", (largura, altura), VALORES_CLASSES["fundo"])
    ImageDraw.Draw(mascara).rectangle(
        caixa_placa_inclusiva,
        fill=VALORES_CLASSES["placa_limpa"],
    )

    if rng.random() < 0.32:
        reflexo = Image.new("RGBA", (largura_placa, altura_placa), (0, 0, 0, 0))
        desenho_reflexo = ImageDraw.Draw(reflexo)
        inicio_x = rng.randint(0, max(0, largura_placa * 2 // 3))
        inicio_y = rng.randint(0, max(0, altura_placa // 2))
        fim_x = min(
            largura_placa,
            inicio_x
            + rng.randint(max(2, largura_placa // 8), max(2, largura_placa // 2)),
        )
        fim_y = min(
            altura_placa,
            inicio_y
            + rng.randint(max(2, altura_placa // 8), max(2, altura_placa // 3)),
        )
        desenho_reflexo.ellipse(
            (inicio_x, inicio_y, fim_x, fim_y),
            fill=(255, 255, 255, rng.randint(48, 112)),
        )
        cena.alpha_composite(
            reflexo.filter(ImageFilter.GaussianBlur(max(1, altura_placa * 0.025))),
            dest=(caixa_placa[0], caixa_placa[1]),
        )

    return cena, mascara, nome_dominante, dominante_rgb


def _criar_campo_luz(largura: int, altura: int, rng: random.Random) -> Image.Image:
    largura_baixa = min(64, max(8, largura // 16))
    altura_baixa = min(48, max(8, altura // 16))
    angulo = rng.uniform(0, math.tau)
    direcao_x = math.cos(angulo)
    direcao_y = math.sin(angulo)
    nivel_base = rng.uniform(0.88, 0.96)
    ruido_direcional = rng.uniform(0.025, 0.085)
    hotspot_x, hotspot_y = rng.uniform(0.2, 0.8), rng.uniform(0.2, 0.8)
    raio_hotspot = rng.uniform(0.18, 0.42)
    intensidade_uv = rng.uniform(0.0, 0.12)
    grade: list[int] = []
    for y in range(altura_baixa):
        for x in range(largura_baixa):
            px = x / max(1, largura_baixa - 1) - 0.5
            py = y / max(1, altura_baixa - 1) - 0.5
            variacao = px * direcao_x + py * direcao_y
            u = x / max(1, largura_baixa - 1)
            v = y / max(1, altura_baixa - 1)
            distancia = ((u - hotspot_x) ** 2 + (v - hotspot_y) ** 2) ** 0.5
            uv = intensidade_uv * math.exp(-((distancia / raio_hotspot) ** 2))
            raio = math.sqrt(px * px + py * py)
            vinheta = max(0.72, 1 - max(0, raio - 0.22) * rng.uniform(0.02, 0.06))
            valor = (
                nivel_base
                + variacao * ruido_direcional
                + uv
                - (1 - vinheta)
                + rng.uniform(-0.012, 0.012)
            )
            grade.append(max(200, min(255, round(valor * 255))))
    campo = Image.new("L", (largura_baixa, altura_baixa))
    campo.putdata(grade)
    return campo.resize((largura, altura), Image.Resampling.BILINEAR)


def _finalizar_cena(
    cena: Image.Image,
    mascara: Image.Image,
    rng: random.Random,
    rng_geometria: random.Random | None = None,
) -> tuple[Image.Image, Image.Image]:
    """Aplica captura, luz, pequena perspectiva, ruído e compressão à cena.

    Args:
        cena: Cena RGB composta.
        mascara: Máscara de três classes da mesma cena.
        rng: Gerador das variações próprias de cada imagem.
        rng_geometria: Gerador da perspectiva e da rotação. Por padrão elas
            saem de ``rng``; um gerador fixo por câmera repete a silhueta.

    Returns:
        Cena e máscara depois da captura simulada.
    """
    luz = _criar_campo_luz(*cena.size, rng).convert("RGB")
    cena_rgb = ImageChops.multiply(cena.convert("RGB"), luz)
    origem_geometria = rng if rng_geometria is None else rng_geometria
    g = origem_geometria.uniform(-0.000012, 0.000012)
    h = origem_geometria.uniform(-0.000012, 0.000012)
    parametros = (
        1.0,
        origem_geometria.uniform(-0.0015, 0.0015),
        origem_geometria.uniform(-1.2, 1.2),
        origem_geometria.uniform(-0.0015, 0.0015),
        1.0,
        origem_geometria.uniform(-1.2, 1.2),
        g,
        h,
    )
    cena_rgb = cena_rgb.transform(
        cena_rgb.size,
        Image.Transform.PERSPECTIVE,
        parametros,
        resample=Image.Resampling.BICUBIC,
        fillcolor=(211, 212, 205),
    )
    mascara = mascara.transform(
        mascara.size,
        Image.Transform.PERSPECTIVE,
        parametros,
        resample=Image.Resampling.NEAREST,
        fillcolor=VALORES_CLASSES["fundo"],
    )
    angulo = origem_geometria.uniform(-1.1, 1.1)
    cena_rgb = cena_rgb.rotate(
        angulo,
        resample=Image.Resampling.BICUBIC,
        expand=False,
        fillcolor=(211, 212, 205),
    )
    mascara = mascara.rotate(
        angulo,
        resample=Image.Resampling.NEAREST,
        expand=False,
        fillcolor=VALORES_CLASSES["fundo"],
    )
    if rng.random() < 0.24:
        cena_rgb = cena_rgb.filter(ImageFilter.GaussianBlur(rng.uniform(0.25, 0.7)))
    if rng.random() < 0.7:
        cena_rgb = _aplicar_ruido_suave(cena_rgb.convert("RGBA"), rng).convert("RGB")
    buffer = io.BytesIO()
    cena_rgb.save(buffer, format="JPEG", quality=rng.randint(86, 96), optimize=False)
    buffer.seek(0)
    with Image.open(buffer) as comprimida:
        cena_rgb = comprimida.convert("RGB")
    return cena_rgb, mascara


def _compor_sprites(
    cena: Image.Image,
    uniao: Image.Image,
    caixa_placa: tuple[int, int, int, int],
    sprites: tuple[SpriteCatalogado, ...],
    percentual_alvo: float,
    rng: random.Random,
    limite_sprites: int,
    pesos_grupo: dict[str, float] | None = None,
    px_por_mm: float = PX_POR_MM_PADRAO,
    k_escala: float = 2.0,
    variacao_escala_minima: float = VARIACAO_ESCALA_MINIMA,
    variacao_escala_maxima: float = VARIACAO_ESCALA_MAXIMA,
    grade_densidade: tuple[int, int] = GRADE_DENSIDADE_PADRAO,
) -> int:
    largura_placa, altura_placa = uniao.size
    area_placa = largura_placa * altura_placa
    pixels_cobertos = 0
    inseridos = 0
    por_grupo = {
        grupo: tuple(sprite for sprite in sprites if sprite.grupo == grupo)
        for grupo in GRUPOS_INSETOS
        if any(sprite.grupo == grupo for sprite in sprites)
    }
    pesos_ativos = _normalizar_pesos_grupo(
        set(por_grupo),
        pesos_grupo or PESOS_GRUPO_PADRAO,
    )
    densidade, acumulados, soma_densidade = _criar_mapa_densidade(
        largura_placa,
        altura_placa,
        grade_densidade,
        rng,
    )
    tolerancia_pixels = max(1, math.ceil(area_placa * TOLERANCIA_COBERTURA_PP / 100.0))
    alvo_pixels = round(area_placa * percentual_alvo / 100.0)
    cobertura_maxima_pixels = math.floor(area_placa * 35.0 / 100.0)
    alvo_composicao = min(
        cobertura_maxima_pixels,
        alvo_pixels + max(1, round(area_placa * 0.25 / 100.0)),
    )
    margem_parada = max(1, round(area_placa * 0.12 / 100.0))

    for _ in range(limite_sprites):
        restante_pixels = alvo_composicao - pixels_cobertos
        if restante_pixels <= margem_parada:
            break
        grupo = rng.choices(
            tuple(pesos_ativos),
            weights=tuple(pesos_ativos.values()),
            k=1,
        )[0]
        por_categoria = {
            categoria: tuple(
                sprite for sprite in por_grupo[grupo] if sprite.categoria == categoria
            )
            for categoria in CATEGORIAS
        }
        categorias_disponiveis = tuple(
            categoria for categoria, candidatos in por_categoria.items() if candidatos
        )
        restante_pp = restante_pixels * 100.0 / area_placa
        categoria = _escolher_categoria(restante_pp, rng, categorias_disponiveis)
        fragmentos = tuple(
            sprite for sprite in por_categoria[categoria] if sprite.fragmentado
        )
        if fragmentos and rng.random() < 0.12:
            sprite = rng.choice(fragmentos)
        else:
            sprite = rng.choice(por_categoria[categoria])
        sprite_rgba = _transformar_sprite(
            sprite,
            px_por_mm,
            k_escala,
            rng.uniform(variacao_escala_minima, variacao_escala_maxima),
            largura_placa,
            altura_placa,
            rng,
        )
        silhueta = _mascara_sprite(sprite_rgba)
        if silhueta.getbbox() is None:
            continue
        area_sprite = silhueta.histogram()[255]
        cobertura_nova_minima = max(1, round(area_sprite * 0.2))

        melhor_caixa: tuple[int, int, int, int] | None = None
        melhor_regiao: Image.Image | None = None
        melhor_cobertura_nova = 0
        for _ in range(TENTATIVAS_POR_SPRITE):
            x_local, y_local = _amostrar_posicao_densa(
                acumulados,
                soma_densidade,
                densidade,
                largura_placa,
                altura_placa,
                silhueta.size,
                rng,
            )
            caixa_local = (
                x_local,
                y_local,
                x_local + silhueta.width,
                y_local + silhueta.height,
            )
            regiao_existente = uniao.crop(caixa_local)
            pixels_novos = ImageChops.multiply(
                silhueta,
                ImageChops.invert(regiao_existente),
            )
            novos = pixels_novos.histogram()[255]
            if novos < cobertura_nova_minima:
                continue
            if (
                pixels_cobertos + novos
                <= min(alvo_pixels + tolerancia_pixels, cobertura_maxima_pixels)
                and novos > melhor_cobertura_nova
            ):
                melhor_caixa = caixa_local
                melhor_regiao = regiao_existente
                melhor_cobertura_nova = novos

        if melhor_caixa is None and restante_pixels > margem_parada:
            for _ in range(TENTATIVAS_POR_SPRITE * 2):
                x_local = rng.randint(0, max(0, largura_placa - silhueta.width))
                y_local = rng.randint(0, max(0, altura_placa - silhueta.height))
                caixa_local = (
                    x_local,
                    y_local,
                    x_local + silhueta.width,
                    y_local + silhueta.height,
                )
                regiao_existente = uniao.crop(caixa_local)
                pixels_novos = ImageChops.multiply(
                    silhueta,
                    ImageChops.invert(regiao_existente),
                )
                novos = pixels_novos.histogram()[255]
                if (
                    novos >= cobertura_nova_minima
                    and novos > melhor_cobertura_nova
                    and pixels_cobertos + novos
                    <= min(alvo_pixels + tolerancia_pixels, cobertura_maxima_pixels)
                ):
                    melhor_caixa = caixa_local
                    melhor_regiao = regiao_existente
                    melhor_cobertura_nova = novos

        if melhor_caixa is None and restante_pixels > margem_parada:
            area_atual_sprite = silhueta.histogram()[255]
            area_permitida = restante_pixels + tolerancia_pixels
            fator = min(0.92, math.sqrt(area_permitida / max(1, area_atual_sprite)))
            if fator >= 0.2:
                sprite_rgba = _redimensionar_sprite(sprite_rgba, fator)
                silhueta = _mascara_sprite(sprite_rgba)
                area_sprite = silhueta.histogram()[255]
                cobertura_nova_minima = max(1, round(area_sprite * 0.2))
                for _ in range(TENTATIVAS_POR_SPRITE):
                    x_local, y_local = _amostrar_posicao_densa(
                        acumulados,
                        soma_densidade,
                        densidade,
                        largura_placa,
                        altura_placa,
                        silhueta.size,
                        rng,
                    )
                    caixa_local = (
                        x_local,
                        y_local,
                        x_local + silhueta.width,
                        y_local + silhueta.height,
                    )
                    regiao_existente = uniao.crop(caixa_local)
                    pixels_novos = ImageChops.multiply(
                        silhueta,
                        ImageChops.invert(regiao_existente),
                    )
                    novos = pixels_novos.histogram()[255]
                    if (
                        novos >= cobertura_nova_minima
                        and novos > melhor_cobertura_nova
                        and pixels_cobertos + novos
                        <= min(alvo_pixels + tolerancia_pixels, cobertura_maxima_pixels)
                    ):
                        melhor_caixa = caixa_local
                        melhor_regiao = regiao_existente
                        melhor_cobertura_nova = novos

        if melhor_caixa is None or melhor_regiao is None:
            continue

        uniao.paste(
            ImageChops.lighter(melhor_regiao, silhueta),
            melhor_caixa,
        )
        posicao_global = (
            caixa_placa[0] + melhor_caixa[0],
            caixa_placa[1] + melhor_caixa[1],
        )
        _compor_sombra_contato(cena, sprite_rgba, posicao_global, rng)
        cena.alpha_composite(sprite_rgba, dest=posicao_global)
        pixels_cobertos += melhor_cobertura_nova
        inseridos += 1

    return inseridos


def _criar_mapa_densidade(
    largura: int,
    altura: int,
    dimensoes: tuple[int, int],
    rng: random.Random,
) -> tuple[tuple[int, int], tuple[float, ...], float]:
    """Mistura pontos uniformes, focos, gradiente e reforço de borda."""
    colunas, linhas = dimensoes
    focos = [
        (
            rng.uniform(0.12, 0.88),
            rng.uniform(0.12, 0.88),
            rng.uniform(0.18, 0.52),
            rng.uniform(0.08, 0.2),
            rng.uniform(0.08, 0.2),
        )
        for _ in range(rng.randint(1, 4))
    ]
    angulo = rng.uniform(0, math.tau)
    direcao_x, direcao_y = math.cos(angulo), math.sin(angulo)
    forca_gradiente = rng.uniform(0.15, 0.75)
    forca_borda = rng.uniform(0.08, 0.55)
    peso_uniforme = rng.uniform(0.12, 0.42)
    pesos: list[float] = []
    for linha in range(linhas):
        y = (linha + 0.5) / linhas
        for coluna in range(colunas):
            x = (coluna + 0.5) / colunas
            agrupamento = sum(
                peso
                * math.exp(
                    -(
                        (x - centro_x) ** 2 / (2 * sigma_x**2)
                        + (y - centro_y) ** 2 / (2 * sigma_y**2)
                    )
                )
                for centro_x, centro_y, peso, sigma_x, sigma_y in focos
            )
            direcao = ((x - 0.5) * direcao_x + (y - 0.5) * direcao_y) * 2
            gradiente = max(0.25, 1 + direcao * forca_gradiente)
            distancia_borda = min(x, 1 - x, y, 1 - y)
            borda = 1 + forca_borda * math.exp(-distancia_borda * 12)
            pesos.append((peso_uniforme + agrupamento) * gradiente * borda)
    acumulados: list[float] = []
    soma = 0.0
    for peso in pesos:
        soma += peso
        acumulados.append(soma)
    return (colunas, linhas), tuple(acumulados), soma


def _amostrar_posicao_densa(
    acumulados: tuple[float, ...],
    soma_densidade: float,
    dimensoes: tuple[int, int],
    largura: int,
    altura: int,
    tamanho: tuple[int, int],
    rng: random.Random,
) -> tuple[int, int]:
    colunas, linhas = dimensoes
    indice = bisect.bisect_left(acumulados, rng.random() * soma_densidade)
    indice = min(indice, len(acumulados) - 1)
    coluna, linha = indice % colunas, indice // colunas
    largura_objeto, altura_objeto = tamanho
    max_x = max(0, largura - largura_objeto)
    max_y = max(0, altura - altura_objeto)
    x0 = min(max_x, round(coluna * largura / colunas))
    x1 = min(max_x, round((coluna + 1) * largura / colunas))
    y0 = min(max_y, round(linha * altura / linhas))
    y1 = min(max_y, round((linha + 1) * altura / linhas))
    return rng.randint(x0, max(x0, x1)), rng.randint(y0, max(y0, y1))


def _mascara_sprite(sprite: Image.Image) -> Image.Image:
    return sprite.getchannel("A").point(lambda valor: 255 if valor > 127 else 0)


def _redimensionar_sprite(sprite: Image.Image, fator: float) -> Image.Image:
    largura = max(1, round(sprite.width * fator))
    altura = max(1, round(sprite.height * fator))
    return sprite.resize((largura, altura), Image.Resampling.LANCZOS)


def _compor_sombra_contato(
    cena: Image.Image,
    sprite: Image.Image,
    destino: tuple[int, int],
    rng: random.Random,
) -> None:
    alfa = sprite.getchannel("A").filter(ImageFilter.GaussianBlur(0.8))
    opacidade = rng.uniform(0.18, 0.32)
    alfa = alfa.point(lambda valor: round(valor * opacidade))
    sombra = Image.new("RGBA", sprite.size, (28, 28, 24, 0))
    sombra.putalpha(alfa)
    dx, dy = rng.choice((1, 2)), rng.choice((1, 2))
    sombra = sombra.transform(
        sombra.size,
        Image.Transform.AFFINE,
        (1, 0, -dx, 0, 1, -dy),
        resample=Image.Resampling.BILINEAR,
    )
    cena.alpha_composite(sombra, dest=destino)


def _escolher_categoria(
    restante_pp: float,
    rng: random.Random,
    disponiveis: tuple[str, ...] = CATEGORIAS,
) -> CategoriaSprite:
    if restante_pp > 7:
        pesos = (0.20, 0.45, 0.35)
    elif restante_pp > 1.2:
        pesos = (0.48, 0.40, 0.12)
    else:
        pesos = (0.84, 0.16, 0.0)
    pesos_disponiveis = tuple(
        peso
        for categoria, peso in zip(CATEGORIAS, pesos, strict=True)
        if categoria in disponiveis
    )
    categorias_disponiveis = tuple(
        categoria for categoria in CATEGORIAS if categoria in disponiveis
    )
    escolhida = rng.choices(
        categorias_disponiveis,
        weights=pesos_disponiveis,
        k=1,
    )[0]
    return cast(CategoriaSprite, escolhida)


def _normalizar_pesos_grupo(
    grupos_disponiveis: set[str],
    pesos_configurados: dict[str, float],
) -> dict[str, float]:
    """Normaliza os pesos sem atribuir probabilidade a grupos ausentes."""
    pesos_ativos = {
        grupo: pesos_configurados.get(grupo, 0.0)
        for grupo in GRUPOS_INSETOS
        if grupo in grupos_disponiveis and pesos_configurados.get(grupo, 0.0) > 0
    }
    total = sum(pesos_ativos.values())
    if total <= 0:
        raise ValueError("Nenhum grupo disponível recebeu peso positivo.")
    return {grupo: peso / total for grupo, peso in pesos_ativos.items()}


def _transformar_sprite(
    sprite: SpriteCatalogado,
    px_por_mm: float,
    k_escala: float,
    variacao_escala: float,
    largura_placa: int,
    altura_placa: int,
    rng: random.Random,
) -> Image.Image:
    imagem = sprite.imagem
    alfa = imagem.getchannel("A")
    if max(imagem.size) >= 8:
        alfa = alfa.filter(ImageFilter.MinFilter(3))
    alfa = alfa.filter(ImageFilter.GaussianBlur(0.25))
    imagem = imagem.copy()
    imagem.putalpha(alfa)
    imagem = imagem.rotate(
        rng.uniform(-180, 180),
        resample=Image.Resampling.BICUBIC,
        expand=True,
    )
    tamanho_mm = (
        sprite.tamanho_mm
        or {
            "pequeno": 1.3,
            "medio": 2.4,
            "grande": 4.2,
        }[sprite.categoria]
    )
    dimensao_maxima = max(1, round(tamanho_mm * px_por_mm * k_escala * variacao_escala))
    fator = min(
        dimensao_maxima / max(imagem.size),
        largura_placa / imagem.width,
        altura_placa / imagem.height,
    )
    largura = max(1, round(imagem.width * fator))
    altura = max(1, round(imagem.height * fator))
    imagem = imagem.resize((largura, altura), Image.Resampling.LANCZOS)
    brilho = ImageEnhance.Brightness(imagem.convert("RGB")).enhance(
        rng.uniform(0.76, 1.22)
    )
    resultado = brilho.convert("RGBA")
    resultado.putalpha(imagem.getchannel("A"))
    return resultado


def _selecionar_distratores(rng: random.Random) -> list[str]:
    return [nome for nome, chance in FREQUENCIAS_DISTRATORES if rng.random() < chance]


def _desenhar_distratores(
    cena: Image.Image,
    caixa_placa: tuple[int, int, int, int],
    distratores: list[str],
    rng: random.Random,
) -> None:
    largura = caixa_placa[2] - caixa_placa[0]
    altura = caixa_placa[3] - caixa_placa[1]
    camada = Image.new("RGBA", (largura, altura), (0, 0, 0, 0))
    desenho = ImageDraw.Draw(camada)

    if "poeira" in distratores:
        for _ in range(rng.randint(10, 32)):
            x = rng.randrange(largura)
            y = rng.randrange(altura)
            raio_x = rng.randint(2, max(2, largura // 28))
            raio_y = rng.randint(2, max(2, altura // 14))
            tom = rng.randint(76, 148)
            desenho.ellipse(
                (x - raio_x, y - raio_y, x + raio_x, y + raio_y),
                fill=(
                    tom,
                    max(0, tom - rng.randint(0, 18)),
                    max(0, tom - 24),
                    rng.randint(16, 62),
                ),
            )
        camada = camada.filter(ImageFilter.GaussianBlur(radius=rng.uniform(1.0, 4.0)))
        desenho = ImageDraw.Draw(camada)

    if "teia" in distratores:
        centro_x = rng.randint(0, largura - 1)
        centro_y = rng.randint(0, altura - 1)
        pontos = [
            (rng.randint(0, largura - 1), rng.randint(0, altura - 1))
            for _ in range(rng.randint(4, 8))
        ]
        for ponto in pontos:
            desenho.line((centro_x, centro_y, *ponto), fill=(74, 75, 78, 120), width=1)
        for indice in range(len(pontos)):
            desenho.line(
                (*pontos[indice], *pontos[(indice + 1) % len(pontos)]),
                fill=(91, 92, 95, 86),
                width=1,
            )

    if "pelos" in distratores:
        for _ in range(rng.randint(1, 4)):
            x = rng.randint(0, largura - 1)
            y = rng.randint(0, altura - 1)
            pontos = [(x, y)]
            for _ in range(rng.randint(3, 6)):
                x = max(
                    0, min(largura - 1, x + rng.randint(-largura // 10, largura // 10))
                )
                y = max(0, min(altura - 1, y + rng.randint(-altura // 5, altura // 5)))
                pontos.append((x, y))
            desenho.line(
                pontos, fill=(71, 69, 64, rng.randint(90, 160)), width=rng.randint(1, 3)
            )

    if "respingos" in distratores:
        for _ in range(rng.randint(3, 12)):
            x = rng.randint(0, largura - 1)
            y = rng.randint(0, altura - 1)
            raio = rng.randint(1, max(1, altura // 40))
            desenho.ellipse(
                (x - raio, y - raio, x + raio, y + raio),
                fill=(
                    rng.randint(92, 150),
                    rng.randint(35, 80),
                    rng.randint(28, 58),
                    rng.randint(55, 130),
                ),
            )

    cena.alpha_composite(camada, dest=(caixa_placa[0], caixa_placa[1]))


def _aplicar_ruido_suave(cena: Image.Image, rng: random.Random) -> Image.Image:
    largura, altura = cena.size
    largura_baixa = max(8, largura // 6)
    altura_baixa = max(8, altura // 6)
    ruido_baixo = Image.new("L", (largura_baixa, altura_baixa))
    ruido_baixo.putdata(
        [rng.randint(100, 156) for _ in range(largura_baixa * altura_baixa)]
    )
    ruido = ruido_baixo.resize((largura, altura), Image.Resampling.BICUBIC)
    escala = rng.uniform(0.08, 0.18)
    mapa = ruido.point(
        lambda valor: max(0, min(255, round(128 + (valor - 128) * escala)))
    )
    ruido_rgb = Image.merge("RGB", (mapa, mapa, mapa))
    imagem_rgb = ImageChops.add(
        cena.convert("RGB"),
        ruido_rgb,
        scale=1.0,
        offset=-128,
    )
    return imagem_rgb.convert("RGBA")


def _criar_faixas_estratificadas(quantidade: int, semente: int) -> list[int]:
    base, resto = divmod(quantidade, len(FAIXAS_COBERTURA))
    indices = [faixa for faixa in range(len(FAIXAS_COBERTURA)) for _ in range(base)]
    indices.extend(range(resto))
    random.Random(semente ^ 0x5EED5EED).shuffle(indices)
    return indices


def _criar_divisoes(quantidade: int, semente: int) -> list[str]:
    indices = list(range(quantidade))
    random.Random(semente ^ 0xA11CE).shuffle(indices)
    quantidade_treino = int(quantidade * 0.70)
    quantidade_validacao = int(quantidade * 0.15)
    divisoes = [""] * quantidade
    for indice in indices[:quantidade_treino]:
        divisoes[indice] = "treino"
    for indice in indices[quantidade_treino : quantidade_treino + quantidade_validacao]:
        divisoes[indice] = "validacao"
    for indice in indices[quantidade_treino + quantidade_validacao :]:
        divisoes[indice] = "teste"
    return divisoes
