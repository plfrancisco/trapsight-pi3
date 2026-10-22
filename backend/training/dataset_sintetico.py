"""Gera imagens rotuladas de refis adesivos a partir de sprites catalogados.

O módulo cria cenas, une as silhuetas na máscara de três classes e registra a
cobertura medida no resultado final. Sprites precisam ser PNGs com canal alfa
e licença documentada no manifesto local.
"""

from __future__ import annotations

import json
import math
import platform
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

import PIL
from PIL import Image, ImageChops, ImageDraw, ImageFilter

CategoriaSprite = Literal["pequeno", "medio", "grande"]
FaixaCobertura = Literal["ok", "atencao", "trocar"]

VALORES_CLASSES = {"fundo": 0, "placa_limpa": 1, "placa_coberta": 2}
FAIXAS_COBERTURA: tuple[tuple[FaixaCobertura, float, float], ...] = (
    ("ok", 0.0, 40.0),
    ("atencao", 40.0, 70.0),
    ("trocar", 70.0, 100.0),
)
LARGURA_MODELO = 768
ALTURA_MODELO = 576
RESOLUCAO_PADRAO = (LARGURA_MODELO * 2, ALTURA_MODELO * 2)
TOLERANCIA_COBERTURA_PP = 2.0
LIMITE_SPRITES_POR_AMOSTRA = 2400
TENTATIVAS_POR_SPRITE = 10
CATEGORIAS = ("pequeno", "medio", "grande")
GRUPOS_INSETOS = ("mosca", "mosquito", "formiga", "barata", "mariposa", "besouro")
PESOS_GRUPO_PADRAO = {
    "mosca": 0.70 / 3,
    "mosquito": 0.70 / 3,
    "mariposa": 0.70 / 3,
    "formiga": 0.30 / 3,
    "barata": 0.30 / 3,
    "besouro": 0.30 / 3,
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
    """

    diretorio_saida: Path
    semente: int
    idade_maxima_dias: float
    quantidade: int = 3000
    resolucao: tuple[int, int] = RESOLUCAO_PADRAO
    limite_sprites: int = LIMITE_SPRITES_POR_AMOSTRA
    pesos_grupo: dict[str, float] | None = None

    def __post_init__(self) -> None:
        if self.quantidade < 1:
            raise ValueError("A quantidade precisa ser maior que zero.")
        if not math.isfinite(self.idade_maxima_dias) or self.idade_maxima_dias <= 0:
            raise ValueError("A idade máxima precisa ser um número positivo.")
        if self.limite_sprites < 1:
            raise ValueError("O limite de sprites precisa ser maior que zero.")
        pesos = (
            dict(PESOS_GRUPO_PADRAO)
            if self.pesos_grupo is None
            else dict(self.pesos_grupo)
        )
        if not pesos or set(pesos) - set(GRUPOS_INSETOS):
            raise ValueError("Os pesos precisam usar apenas os seis grupos de insetos.")
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
        alvo_atingido: Indica se a máscara ficou a até dois pontos do alvo.
    """

    imagem: Image.Image
    mascara: Image.Image
    percentual_cobertura_real: float
    n_sprites: int
    distratores_presentes: list[str]
    dominante_cor: str
    dominante_rgb: tuple[int, int, int]
    alvo_atingido: bool


@dataclass(frozen=True)
class GeometriaPlaca:
    """Dimensões fixas da placa adesiva dentro de uma cena."""

    resolucao: tuple[int, int]
    caixa: tuple[int, int, int, int]
    margem_moldura: int


def create_plate_geometry(
    resolucao: tuple[int, int],
    rng: random.Random,
) -> GeometriaPlaca:
    """Sorteia a posição e as dimensões de uma placa para reutilização."""
    largura, altura = resolucao
    if largura < 100 or altura < 100:
        raise ValueError("Cada dimensão da resolução precisa ter ao menos 100 pixels.")
    caixa, margem = _calcular_caixa_placa(largura, altura, rng)
    return GeometriaPlaca(resolucao, caixa, margem)


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
    if not any(sprite.fragmentado for sprite in sprites):
        raise ValueError("O banco precisa incluir sprites de fragmentos de insetos.")
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
        geometria_placa = create_plate_geometry(resolucao, rng)
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
    quantidade_sprites = _compor_sprites(
        cena,
        uniao,
        caixa_placa,
        sprites,
        percentual_alvo,
        rng,
        limite_sprites,
        pesos_grupo,
    )
    mascara.paste(VALORES_CLASSES["placa_coberta"], caixa_placa, uniao)

    distratores = _selecionar_distratores(rng)
    _desenhar_distratores(cena, caixa_placa, distratores, rng)
    if rng.random() < 0.22:
        cena = cena.filter(ImageFilter.GaussianBlur(radius=rng.uniform(0.25, 1.1)))
    if rng.random() < 0.28:
        cena = _aplicar_ruido_suave(cena, rng)

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
        <= TOLERANCIA_COBERTURA_PP,
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
                "idade_simulada_dias": idade_simulada,
                "n_sprites": amostra.n_sprites,
                "distratores_presentes": amostra.distratores_presentes,
                "dominante_cor": amostra.dominante_cor,
                "dominante_rgb": list(amostra.dominante_rgb),
                "alvo_atingido": amostra.alvo_atingido,
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
            }
            for sprite in sprites
        ],
        "proporcoes_conjuntos": {"treino": 0.70, "validacao": 0.15, "teste": 0.15},
        "classes_mascara": VALORES_CLASSES,
        "versao_gerador": 1,
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


def _calcular_caixa_placa(
    largura: int,
    altura: int,
    rng: random.Random,
) -> tuple[tuple[int, int, int, int], int]:
    largura_placa = int(largura * rng.uniform(0.56, 0.78))
    altura_placa = int(largura_placa * 220 / 450)
    altura_maxima = int(altura * 0.62)
    if altura_placa > altura_maxima:
        altura_placa = altura_maxima
        largura_placa = int(altura_placa * 450 / 220)
    margem_moldura = max(3, int(altura_placa * rng.uniform(0.06, 0.12)))
    largura_externa = largura_placa + margem_moldura * 2
    altura_externa = altura_placa + margem_moldura * 2
    margem_x = max(1, int(largura * 0.025))
    margem_y = max(1, int(altura * 0.025))
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
    violeta = rng.random() < 0.62
    forca_violeta = rng.uniform(0.38, 0.95) if violeta else rng.uniform(0.0, 0.18)
    cor_nova = (247.0, 246.0, 235.0)
    cor_envelhecida = (190.0, 165.0, 94.0)
    cor_base = tuple(
        round(nova * (1 - idade_relativa) + velha * idade_relativa)
        for nova, velha in zip(cor_nova, cor_envelhecida, strict=True)
    )
    cor_tinta = (132.0, 142.0, 207.0)
    dominante_rgb = tuple(
        max(0, min(255, round(base * (1 - forca_violeta) + tinta * forca_violeta)))
        for base, tinta in zip(cor_base, cor_tinta, strict=True)
    )
    nome_dominante = "violeta_azulada" if violeta else "branco_corrigido"

    ambiente = (174, 175, 189) if violeta else (219, 218, 213)
    cena = Image.new("RGB", (largura, altura), ambiente)
    luz = _criar_campo_luz(largura, altura, rng)
    cena = ImageChops.multiply(cena, luz.convert("RGB"))
    cena = cena.convert("RGBA")

    caixa_moldura = (
        caixa_placa[0] - margem_moldura,
        caixa_placa[1] - margem_moldura,
        caixa_placa[2] + margem_moldura,
        caixa_placa[3] + margem_moldura,
    )
    sombra_presente = rng.random() < 0.42
    if sombra_presente:
        sombra = Image.new("RGBA", (largura, altura), (0, 0, 0, 0))
        desenho_sombra = ImageDraw.Draw(sombra)
        deslocamento = max(2, int(altura_placa * 0.025))
        caixa_sombra = (
            caixa_moldura[0] + deslocamento,
            caixa_moldura[1] + deslocamento,
            caixa_moldura[2] + deslocamento,
            caixa_moldura[3] + deslocamento,
        )
        desenho_sombra.rounded_rectangle(
            (
                caixa_sombra[0],
                caixa_sombra[1],
                caixa_sombra[2] - 1,
                caixa_sombra[3] - 1,
            ),
            radius=max(2, margem_moldura // 3),
            fill=(18, 22, 36, rng.randint(32, 78)),
        )
        cena.alpha_composite(
            sombra.filter(ImageFilter.GaussianBlur(max(1, margem_moldura / 2)))
        )

    desenho = ImageDraw.Draw(cena)
    cor_moldura = rng.choice(
        ((224, 224, 218, 255), (206, 209, 208, 255), (238, 236, 226, 255))
    )
    desenho.rounded_rectangle(
        (
            caixa_moldura[0],
            caixa_moldura[1],
            caixa_moldura[2] - 1,
            caixa_moldura[3] - 1,
        ),
        radius=max(2, margem_moldura // 3),
        fill=cor_moldura,
        outline=(116, 119, 126, 255),
        width=max(1, margem_moldura // 12),
    )
    caixa_placa_inclusiva = (
        caixa_placa[0],
        caixa_placa[1],
        caixa_placa[2] - 1,
        caixa_placa[3] - 1,
    )
    desenho.rectangle(caixa_placa_inclusiva, fill=(*dominante_rgb, 255))

    mascara = Image.new("L", (largura, altura), VALORES_CLASSES["fundo"])
    ImageDraw.Draw(mascara).rectangle(
        caixa_placa_inclusiva,
        fill=VALORES_CLASSES["placa_limpa"],
    )

    if sombra_presente:
        camada_sombra_placa = Image.new(
            "RGBA", (largura_placa, altura_placa), (0, 0, 0, 0)
        )
        desenho_sombra_placa = ImageDraw.Draw(camada_sombra_placa)
        faixa = max(2, int(altura_placa * rng.uniform(0.025, 0.07)))
        desenho_sombra_placa.rectangle(
            (0, 0, largura_placa - 1, faixa - 1),
            fill=(40, 41, 53, rng.randint(25, 68)),
        )
        sombra_suave = camada_sombra_placa.filter(
            ImageFilter.GaussianBlur(max(1, faixa / 2))
        )
        cena.alpha_composite(sombra_suave, dest=(caixa_placa[0], caixa_placa[1]))

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
    largura_baixa = min(48, max(8, largura // 24))
    altura_baixa = min(36, max(8, altura // 24))
    angulo = rng.uniform(0, math.tau)
    direcao_x = math.cos(angulo)
    direcao_y = math.sin(angulo)
    grade: list[int] = []
    ruido_direcional = rng.uniform(0.14, 0.32)
    nivel_base = rng.uniform(0.72, 0.86)
    for y in range(altura_baixa):
        for x in range(largura_baixa):
            px = x / max(1, largura_baixa - 1) - 0.5
            py = y / max(1, altura_baixa - 1) - 0.5
            variacao = px * direcao_x + py * direcao_y
            valor = (
                nivel_base + variacao * ruido_direcional + rng.uniform(-0.035, 0.035)
            )
            grade.append(max(148, min(255, round(valor * 255))))
    campo = Image.new("L", (largura_baixa, altura_baixa))
    campo.putdata(grade)
    return campo.resize((largura, altura), Image.Resampling.BILINEAR)


def _compor_sprites(
    cena: Image.Image,
    uniao: Image.Image,
    caixa_placa: tuple[int, int, int, int],
    sprites: tuple[SpriteCatalogado, ...],
    percentual_alvo: float,
    rng: random.Random,
    limite_sprites: int,
    pesos_grupo: dict[str, float] | None = None,
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

    for _ in range(limite_sprites):
        percentual_atual = pixels_cobertos * 100.0 / area_placa
        restante = percentual_alvo - percentual_atual
        if restante <= TOLERANCIA_COBERTURA_PP * 0.75:
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
        categoria = _escolher_categoria(restante, rng, categorias_disponiveis)
        fragmentos = tuple(
            sprite for sprite in por_categoria[categoria] if sprite.fragmentado
        )
        if fragmentos and rng.random() < 0.12:
            sprite = rng.choice(fragmentos)
        else:
            sprite = rng.choice(por_categoria[categoria])
        limite_area = FRACOES_AREA_SPRITES[categoria][1]
        fracao_desejada = min(
            restante / 100.0 * rng.uniform(0.35, 0.72),
            limite_area,
        )
        sprite_rgba = _transformar_sprite(
            sprite,
            max(1, round(area_placa * fracao_desejada)),
            largura_placa,
            altura_placa,
            rng,
        )
        silhueta = sprite_rgba.getchannel("A").point(
            lambda valor: 255 if valor >= 128 else 0
        )
        if silhueta.getbbox() is None:
            continue

        melhor_caixa: tuple[int, int, int, int] | None = None
        melhor_regiao: Image.Image | None = None
        melhor_cobertura_nova = 0
        for _ in range(TENTATIVAS_POR_SPRITE):
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
            if novos == 0:
                continue
            percentual_novo = (pixels_cobertos + novos) * 100.0 / area_placa
            if (
                percentual_novo <= percentual_alvo + TOLERANCIA_COBERTURA_PP
                and novos > melhor_cobertura_nova
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
        cena.alpha_composite(
            sprite_rgba,
            dest=(caixa_placa[0] + melhor_caixa[0], caixa_placa[1] + melhor_caixa[1]),
        )
        pixels_cobertos += melhor_cobertura_nova
        inseridos += 1

    return inseridos


def _escolher_categoria(
    restante_pp: float,
    rng: random.Random,
    disponiveis: tuple[str, ...] = CATEGORIAS,
) -> CategoriaSprite:
    if restante_pp > 18:
        pesos = (0.12, 0.28, 0.60)
    elif restante_pp > 6:
        pesos = (0.25, 0.55, 0.20)
    else:
        pesos = (0.75, 0.23, 0.02)
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
    area_desejada: int,
    largura_placa: int,
    altura_placa: int,
    rng: random.Random,
) -> Image.Image:
    imagem = sprite.imagem
    pixels_alfa = sum(
        imagem.getchannel("A")
        .point(lambda valor: 255 if valor >= 128 else 0)
        .histogram()[1:]
    )
    escala = math.sqrt(area_desejada / max(1, pixels_alfa))
    dimensao_maxima = max(
        2, round(altura_placa * LIMITE_ALTURA_SPRITES[sprite.categoria])
    )
    escala = min(
        escala,
        dimensao_maxima / max(imagem.size),
        largura_placa / imagem.width,
        altura_placa / imagem.height,
    )
    largura = max(1, round(imagem.width * escala))
    altura = max(1, round(imagem.height * escala))
    imagem = imagem.resize((largura, altura), Image.Resampling.LANCZOS)
    imagem = imagem.rotate(
        rng.uniform(0, 360), resample=Image.Resampling.BICUBIC, expand=True
    )
    fator = min(
        1.0,
        dimensao_maxima / max(imagem.size),
        largura_placa / imagem.width,
        altura_placa / imagem.height,
    )
    if fator < 1.0:
        imagem = imagem.resize(
            (max(1, round(imagem.width * fator)), max(1, round(imagem.height * fator))),
            Image.Resampling.LANCZOS,
        )
    return imagem


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
