"""Gera imagens rotuladas de refis adesivos a partir de sprites catalogados.

O módulo cria cenas, une as silhuetas na máscara de três classes e registra a
cobertura medida no resultado final. Sprites precisam ser PNGs com canal alfa
e licença documentada no manifesto local.
"""

from __future__ import annotations

import bisect
import io
import json
import math
import platform
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

import PIL
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter

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
    cena, mascara = _finalizar_cena(cena, mascara, rng_finalizacao)

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


def generate_dataset(
    configuracao: ConfiguracaoDataset,
    sprites: tuple[SpriteCatalogado, ...],
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
) -> tuple[Image.Image, Image.Image]:
    """Aplica captura, luz, pequena perspectiva, ruído e compressão à cena."""
    luz = _criar_campo_luz(*cena.size, rng).convert("RGB")
    cena_rgb = ImageChops.multiply(cena.convert("RGB"), luz)
    g = rng.uniform(-0.000012, 0.000012)
    h = rng.uniform(-0.000012, 0.000012)
    parametros = (
        1.0,
        rng.uniform(-0.0015, 0.0015),
        rng.uniform(-1.2, 1.2),
        rng.uniform(-0.0015, 0.0015),
        1.0,
        rng.uniform(-1.2, 1.2),
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
    angulo = rng.uniform(-1.1, 1.1)
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
