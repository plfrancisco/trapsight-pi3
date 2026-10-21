"""Converte anotações COCO poligonais em um catálogo local de sprites RGBA."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import sys
import tempfile
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Literal, cast

from PIL import Image, ImageDraw

from training.coletar_inaturalist import (
    LICENCAS_PERMITIDAS,
    diretorio_dados_configurado,
)

CategoriaSprite = Literal["pequeno", "medio", "grande"]
GrupoInseto = Literal["mosca", "mosquito", "formiga", "barata", "mariposa", "besouro"]
CATEGORIAS = ("pequeno", "medio", "grande")
GRUPOS_INSETOS = ("mosca", "mosquito", "formiga", "barata", "mariposa", "besouro")
LIMITE_PIXELS_IMAGEM = 40_000_000
LIMITE_BYTES_JSON = 100_000_000
AREA_MINIMA_PIXELS = 100
LIMITE_RAZAO_SERRILHADO = 2.0
FRACAO_FRAGMENTOS = 0.15
MINIMO_SPRITES = 300
MINIMO_POR_GRUPO = 20
LIMITE_FRACAO_BORDA_FUNDO = 0.35
DISTANCIA_COR_FUNDO = 38.0


@dataclass(frozen=True)
class ConfiguracaoPreparo:
    """Parâmetros da conversão local de um conjunto COCO.

    Attributes:
        entrada: Diretório do conjunto já baixado.
        saida: Diretório novo ou vazio para o catálogo resultante.
        fonte: Origem pública para conjuntos COCO sem fonte individual.
        licenca: Licença para conjuntos COCO sem licença individual.
        semente: Semente usada para selecionar e recortar fragmentos.
        anotacoes: Caminho opcional do JSON, relativo ao diretório de entrada.
        area_minima_pixels: Área opaca mínima aceita para um inseto inteiro.
        limite_serrilhado: Maior razão perímetro/casco convexo aceita.
        fracao_fragmentos: Proporção de fragmentos produzidos por sprites inteiros.
        minimo_sprites: Quantidade mínima de arquivos no catálogo final.
        minimo_por_grupo: Quantidade mínima de sprites inteiros por grupo.
        grupo_coco: Grupo padrão para categorias COCO sem taxonomia reconhecida.
    """

    entrada: Path
    saida: Path
    semente: int
    fonte: str = ""
    licenca: str = ""
    anotacoes: Path | None = None
    area_minima_pixels: int = AREA_MINIMA_PIXELS
    limite_serrilhado: float = LIMITE_RAZAO_SERRILHADO
    fracao_fragmentos: float = FRACAO_FRAGMENTOS
    minimo_sprites: int = MINIMO_SPRITES
    minimo_por_grupo: int = MINIMO_POR_GRUPO
    grupo_coco: str | None = None

    def __post_init__(self) -> None:
        if self.minimo_por_grupo < 0:
            raise ValueError("O mínimo por grupo não pode ser negativo.")
        if self.grupo_coco is not None and self.grupo_coco not in GRUPOS_INSETOS:
            raise ValueError("O grupo COCO precisa ser um dos seis grupos aceitos.")
        if self.area_minima_pixels < 1:
            raise ValueError("A área mínima precisa ser maior que zero.")
        if not math.isfinite(self.limite_serrilhado) or self.limite_serrilhado < 1:
            raise ValueError("O limite de serrilhado precisa ser finito e ao menos 1.")
        if (
            not math.isfinite(self.fracao_fragmentos)
            or not 0 < self.fracao_fragmentos <= 1
        ):
            raise ValueError("A fração de fragmentos precisa estar entre 0 e 1.")
        if self.minimo_sprites < 3:
            raise ValueError("O mínimo precisa permitir as três categorias de tamanho.")


@dataclass(frozen=True)
class SpritePreparado:
    """Recorte RGBA e metadados de uma anotação ou fragmento derivado."""

    imagem: Image.Image
    area: int
    grupo: GrupoInseto
    autor: str
    fonte: str
    licenca: str
    especie: str | None
    fragmentado: bool
    indice_origem: int
    url_foto: str | None = None


def prepare_sprite_bank(configuracao: ConfiguracaoPreparo) -> dict[str, object]:
    """Gera um catálogo de sprites sem publicar saídas incompletas.

    Args:
        configuracao: Caminhos, procedência, licença e limiares da conversão.

    Returns:
        Relatório escrito junto ao manifesto.

    Raises:
        FileExistsError: Se a saída já contiver arquivos.
        FileNotFoundError: Se o conjunto, manifesto ou imagem não existir.
        ValueError: Se os dados forem inválidos ou o banco ficar abaixo do mínimo.
    """
    raiz = configuracao.entrada.resolve(strict=True)
    if not raiz.is_dir():
        raise ValueError("A entrada precisa ser um diretório de imagens e metadados.")

    manifesto_coleta = raiz / "inaturalist" / "manifesto_coleta.json"
    if manifesto_coleta.is_file():
        pasta_entrada = manifesto_coleta.parent
    else:
        manifesto_coleta = raiz / "manifesto_coleta.json"
        pasta_entrada = raiz
    saida = configuracao.saida.absolute()
    saida_resolvida = saida.resolve()
    if (
        saida_resolvida == pasta_entrada
        or pasta_entrada in saida_resolvida.parents
        or saida_resolvida in pasta_entrada.parents
    ):
        raise ValueError("A saída não pode ficar dentro do conjunto de entrada.")
    if saida.is_symlink():
        raise ValueError("A saída não pode ser um link simbólico.")
    if saida.exists() and (not saida.is_dir() or any(saida.iterdir())):
        raise FileExistsError(f"O diretório de saída não está vazio: {saida}.")

    descartados: Counter[str] = Counter()
    if manifesto_coleta.exists():
        sprites, fotos_baixadas = _extrair_sprites_inaturalist(
            raiz=raiz,
            caminho_manifesto=manifesto_coleta,
            configuracao=configuracao,
            descartados=descartados,
        )
        total_lido = fotos_baixadas
        caminho_json = manifesto_coleta
    else:
        if not configuracao.fonte.strip() or not configuracao.licenca.strip():
            raise ValueError("Conjuntos COCO exigem fonte e licença informadas.")
        caminho_json, dados_coco = _carregar_coco(raiz, configuracao.anotacoes)
        imagens = _validar_imagens(raiz, dados_coco.get("images"))
        categorias = _mapear_categorias(dados_coco.get("categories", []))
        anotacoes = dados_coco.get("annotations")
        if not isinstance(anotacoes, list):
            raise ValueError("O arquivo COCO precisa conter uma lista 'annotations'.")
        sprites = _extrair_sprites(
            imagens=imagens,
            categorias=categorias,
            anotacoes=anotacoes,
            configuracao=configuracao,
            descartados=descartados,
        )
        total_lido = len(anotacoes)
    fragmentos = _gerar_fragmentos(sprites, configuracao, descartados)
    sprites_finais = [*sprites, *fragmentos]
    contagens_por_grupo = Counter(sprite.grupo for sprite in sprites)
    manifesto, contagens_categoria, contagens_grupo = _criar_manifesto(
        sprites_finais, sprites
    )
    insuficientes = {
        grupo: configuracao.minimo_por_grupo - contagens_por_grupo[grupo]
        for grupo in GRUPOS_INSETOS
        if contagens_por_grupo[grupo] < configuracao.minimo_por_grupo
    }
    relatorio_coleta = _carregar_relatorio_coleta(manifesto_coleta)
    problemas = []
    if len(sprites_finais) < configuracao.minimo_sprites:
        problemas.append(
            "mínimo total não atingido: foram preparados "
            f"{len(sprites_finais)} sprites, mas o mínimo configurado é "
            f"{configuracao.minimo_sprites}"
        )
    if not fragmentos:
        problemas.append("nenhum fragmento válido foi produzido")
    if insuficientes:
        problemas.append(
            "são necessários ao menos "
            f"{configuracao.minimo_por_grupo} sprites inteiros por grupo: "
            + ", ".join(
                f"{grupo}={contagens_por_grupo[grupo]}" for grupo in insuficientes
            )
        )
    relatorio: dict[str, object] = {
        "fotos_baixadas": total_lido if manifesto_coleta.exists() else 0,
        "fotos_por_grupo": relatorio_coleta.get("fotos_por_grupo", {}),
        "fotos_por_taxon": relatorio_coleta.get("fotos_por_taxon", {}),
        "coleta_descartados_por_motivo": relatorio_coleta.get(
            "descartados_por_motivo", {}
        ),
        "recortes_lidos": total_lido,
        "recortes_aceitos": len(sprites),
        "sprites_aceitos": len(sprites_finais),
        "descartados_por_motivo": {
            motivo: descartados[motivo]
            for motivo in (
                "sem_poligono",
                "rle",
                "area_minima",
                "bordas_serrilhadas",
                "fundo_residual",
                "duplicado",
                "licenca_nao_permitida",
                "falha_segmentacao",
                "grupo_desconhecido",
                "registro_invalido",
                "mascara_vazia",
            )
        },
        "sprites_por_categoria": contagens_categoria,
        "sprites_por_grupo": contagens_grupo,
        "sprites_inteiros_por_grupo": dict(contagens_por_grupo),
        "numero_fragmentos": len(fragmentos),
        "semente": configuracao.semente,
        "area_minima_pixels": configuracao.area_minima_pixels,
        "limite_serrilhado": configuracao.limite_serrilhado,
        "fracao_fragmentos_solicitada": configuracao.fracao_fragmentos,
        "arquivo_entrada": caminho_json.name,
        "metas_atingidas": not problemas,
        "motivos_falha": problemas,
    }
    _gravar_relatorio_preparo(saida.parent, relatorio)
    if problemas:
        raise ValueError("Banco incompleto: " + "; ".join(problemas) + ".")
    _publicar_banco(saida, manifesto, relatorio, sprites_finais)
    return relatorio


def _carregar_relatorio_coleta(manifesto: Path) -> dict[str, object]:
    """Lê as métricas da coleta associadas ao manifesto de fotos."""
    caminho = manifesto.with_name("relatorio_coleta.json")
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dados if isinstance(dados, dict) else {}


def _gravar_relatorio_preparo(raiz: Path, relatorio: dict[str, object]) -> None:
    """Salva o resultado do processamento junto aos dados de origem."""
    raiz.mkdir(parents=True, exist_ok=True)
    (raiz / "relatorio_preparo.json").write_text(
        json.dumps(relatorio, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _carregar_coco(
    raiz: Path, anotacoes: Path | None
) -> tuple[Path, dict[str, object]]:
    if anotacoes is None:
        candidatos = sorted(raiz.glob("*.json"), key=lambda caminho: caminho.name)
        if len(candidatos) != 1:
            raise ValueError(
                "Informe --anotacoes quando o diretório não tiver exatamente um JSON."
            )
        nome = candidatos[0].name
    else:
        nome = str(anotacoes)

    caminho = _resolver_arquivo_interno(raiz, nome)
    if caminho.stat().st_size > LIMITE_BYTES_JSON:
        raise ValueError("O arquivo de anotações excede o limite de 100 MB.")
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except json.JSONDecodeError as erro:
        raise ValueError("O arquivo de anotações precisa ser JSON válido.") from erro
    if not isinstance(dados, dict):
        raise ValueError("O arquivo de anotações precisa conter um objeto COCO.")
    return caminho, dados


def _resolver_arquivo_interno(raiz: Path, nome: str) -> Path:
    nome_normalizado = nome.replace("\\", "/")
    partes = PurePosixPath(nome_normalizado).parts
    if (
        not nome_normalizado.strip()
        or PurePosixPath(nome_normalizado).is_absolute()
        or PureWindowsPath(nome).drive
        or any(parte == ".." for parte in nome_normalizado.split("/"))
        or any(":" in parte for parte in partes)
    ):
        raise ValueError(f"O caminho escapa da entrada ou é absoluto: {nome}.")
    try:
        caminho = raiz.joinpath(*partes).resolve(strict=True)
    except (OSError, RuntimeError) as erro:
        raise ValueError(
            f"Não foi possível resolver o caminho da entrada: {nome}."
        ) from erro
    if not caminho.is_relative_to(raiz):
        raise ValueError(f"O caminho escapa do diretório de entrada: {nome}.")
    if not caminho.is_file():
        raise ValueError(f"O caminho da entrada não é um arquivo: {nome}.")
    return caminho


def _validar_imagens(
    raiz: Path,
    registros: object,
) -> dict[int | str, tuple[Path, str]]:
    if not isinstance(registros, list):
        raise ValueError("O arquivo COCO precisa conter uma lista 'images'.")
    imagens: dict[int | str, tuple[Path, str]] = {}
    for indice, registro in enumerate(registros):
        if not isinstance(registro, dict):
            raise ValueError(f"O registro de imagem {indice} precisa ser um objeto.")
        identificador = _identificador_coco(registro.get("id"), "imagem", indice)
        nome = registro.get("file_name")
        if not isinstance(nome, str):
            raise ValueError(f"A imagem {indice} precisa declarar 'file_name'.")
        if identificador in imagens:
            raise ValueError(
                f"O identificador da imagem aparece mais de uma vez: {identificador}."
            )
        imagens[identificador] = (_resolver_arquivo_interno(raiz, nome), nome)
    return imagens


def _mapear_categorias(registros: object) -> dict[int | str, str]:
    if not isinstance(registros, list):
        raise ValueError("O campo COCO 'categories' precisa ser uma lista.")
    categorias: dict[int | str, str] = {}
    for indice, registro in enumerate(registros):
        if not isinstance(registro, dict):
            raise ValueError(f"A categoria {indice} precisa ser um objeto.")
        identificador = _identificador_coco(registro.get("id"), "categoria", indice)
        nome = registro.get("name")
        if isinstance(nome, str) and nome.strip():
            categorias[identificador] = nome.strip()
    return categorias


def _identificador_coco(valor: object, tipo: str, indice: int) -> int | str:
    if isinstance(valor, bool) or not isinstance(valor, (int, str)):
        raise ValueError(
            f"O identificador de {tipo} {indice} precisa ser texto ou inteiro."
        )
    return valor


def _extrair_sprites(
    imagens: dict[int | str, tuple[Path, str]],
    categorias: dict[int | str, str],
    anotacoes: list[object],
    configuracao: ConfiguracaoPreparo,
    descartados: Counter[str],
) -> list[SpritePreparado]:
    sprites: list[SpritePreparado] = []
    hashes: set[str] = set()
    for indice, anotacao in enumerate(anotacoes):
        if not isinstance(anotacao, dict):
            raise ValueError(f"A anotação {indice} precisa ser um objeto.")
        id_imagem = _identificador_coco(
            anotacao.get("image_id"), "imagem da anotação", indice
        )
        if id_imagem not in imagens:
            raise ValueError(f"A anotação {indice} referencia uma imagem inexistente.")

        tipo_segmentacao, poligonos = _ler_poligonos(anotacao.get("segmentation"))
        if tipo_segmentacao != "poligonos":
            descartados[tipo_segmentacao] += 1
            continue

        caminho_imagem, _ = imagens[id_imagem]
        sprite, mascara, pontos, fundo_residual = _recortar_anotacao(
            caminho_imagem, poligonos
        )
        if fundo_residual:
            descartados["fundo_residual"] += 1
            continue
        area = mascara.histogram()[255]
        if area < configuracao.area_minima_pixels:
            descartados["area_minima"] += 1
            continue

        perimetro_casco = _perimetro_casco_convexo(pontos)
        perimetro_mascara = _perimetro_mascara(mascara)
        if (
            perimetro_casco == 0
            or perimetro_mascara / perimetro_casco > configuracao.limite_serrilhado
        ):
            descartados["bordas_serrilhadas"] += 1
            continue

        # A máscara vira alfa, impedindo que pixels externos sobrevivam ao recorte.
        alfa = sprite.getchannel("A")
        if alfa.tobytes() != mascara.tobytes():
            descartados["fundo_residual"] += 1
            continue
        assinatura = hashlib.sha256(
            sprite.width.to_bytes(4, "big")
            + sprite.height.to_bytes(4, "big")
            + sprite.tobytes()
        ).hexdigest()
        if assinatura in hashes:
            descartados["duplicado"] += 1
            continue
        hashes.add(assinatura)

        categoria_id = anotacao.get("category_id")
        especie = (
            categorias.get(categoria_id)
            if isinstance(categoria_id, (int, str))
            else None
        )
        grupo = configuracao.grupo_coco or _inferir_grupo(especie)
        if grupo is None:
            descartados["grupo_desconhecido"] += 1
            continue
        sprites.append(
            SpritePreparado(
                imagem=sprite,
                area=area,
                grupo=cast(GrupoInseto, grupo),
                autor="não informado no conjunto COCO",
                fonte=configuracao.fonte.strip(),
                licenca=configuracao.licenca.strip(),
                especie=especie,
                fragmentado=False,
                indice_origem=indice,
            )
        )
    return sprites


def _ler_poligonos(
    segmentacao: object,
) -> tuple[Literal["poligonos", "rle", "sem_poligono"], list[list[tuple[int, int]]]]:
    if isinstance(segmentacao, dict):
        return "rle", []
    if not isinstance(segmentacao, list) or not segmentacao:
        return "sem_poligono", []

    if all(
        isinstance(valor, (int, float)) and not isinstance(valor, bool)
        for valor in segmentacao
    ):
        registros = [segmentacao]
    else:
        registros = segmentacao

    poligonos: list[list[tuple[int, int]]] = []
    for registro in registros:
        if not isinstance(registro, list) or len(registro) < 6 or len(registro) % 2:
            return "sem_poligono", []
        pontos: list[tuple[int, int]] = []
        for indice in range(0, len(registro), 2):
            x, y = registro[indice], registro[indice + 1]
            if (
                isinstance(x, bool)
                or isinstance(y, bool)
                or not isinstance(x, (int, float))
                or not isinstance(y, (int, float))
                or not math.isfinite(x)
                or not math.isfinite(y)
            ):
                return "sem_poligono", []
            pontos.append((round(x), round(y)))
        poligonos.append(pontos)
    return "poligonos", poligonos


def _recortar_anotacao(
    caminho_imagem: Path,
    poligonos: list[list[tuple[int, int]]],
) -> tuple[Image.Image, Image.Image, list[tuple[int, int]], bool]:
    try:
        with Image.open(caminho_imagem) as imagem_aberta:
            largura, altura = imagem_aberta.size
            if largura * altura > LIMITE_PIXELS_IMAGEM:
                raise ValueError(
                    "Uma imagem do conjunto excede o limite de 40 milhões de pixels."
                )
            for poligono in poligonos:
                if any(
                    x < 0 or y < 0 or x > largura or y > altura for x, y in poligono
                ):
                    raise ValueError(
                        "Um polígono de segmentação sai dos limites da imagem."
                    )
            imagem_aberta.load()
            imagem_rgb = imagem_aberta.convert("RGB")
    except Image.DecompressionBombError as erro:
        raise ValueError("Uma imagem do conjunto excede o limite de pixels.") from erro

    mascara_completa = Image.new("L", (largura, altura), 0)
    desenho = ImageDraw.Draw(mascara_completa)
    pontos_todos: list[tuple[int, int]] = []
    for poligono in poligonos:
        pontos_ajustados = [
            (min(largura - 1, x), min(altura - 1, y)) for x, y in poligono
        ]
        desenho.polygon(pontos_ajustados, fill=255)
        pontos_todos.extend(pontos_ajustados)

    caixa = mascara_completa.getbbox()
    if caixa is None:
        caixa = (0, 0, 1, 1)
    mascara = mascara_completa.crop(caixa)
    imagem_recortada = imagem_rgb.crop(caixa)
    fundo = _cor_fundo_borda(imagem_rgb)
    fundo_residual = _borda_parece_fundo(imagem_recortada, mascara, fundo)
    sprite = Image.new("RGBA", imagem_recortada.size, (0, 0, 0, 0))
    sprite.paste(imagem_recortada.convert("RGBA"), (0, 0), mascara)
    return sprite, mascara, pontos_todos, fundo_residual


def _extrair_sprites_inaturalist(
    raiz: Path,
    caminho_manifesto: Path,
    configuracao: ConfiguracaoPreparo,
    descartados: Counter[str],
) -> tuple[list[SpritePreparado], int]:
    if caminho_manifesto.stat().st_size > LIMITE_BYTES_JSON:
        raise ValueError("O manifesto de coleta excede o limite de 100 MB.")
    try:
        manifesto = json.loads(caminho_manifesto.read_text(encoding="utf-8"))
    except json.JSONDecodeError as erro:
        raise ValueError("O manifesto de coleta precisa ser JSON válido.") from erro
    fotos = manifesto.get("fotos") if isinstance(manifesto, dict) else None
    if not isinstance(fotos, list):
        raise ValueError("O manifesto de coleta precisa conter uma lista 'fotos'.")

    diretorio_cache_modelo = raiz / "cache" / "rembg"
    diretorio_cache_modelo.mkdir(parents=True, exist_ok=True)
    os.environ["U2NET_HOME"] = str(diretorio_cache_modelo.resolve())
    try:
        from rembg import new_session, remove
    except ImportError as erro:
        raise ValueError(
            "O recorte de fotos exige o grupo opcional de treino: uv sync --group treino."
        ) from erro
    sessao = new_session("isnet-general-use")

    sprites: list[SpritePreparado] = []
    assinaturas: set[str] = set()
    for indice, registro in enumerate(fotos):
        if not isinstance(registro, dict):
            descartados["registro_invalido"] += 1
            continue
        grupo = registro.get("grupo")
        autor = registro.get("autor")
        licenca = registro.get("licenca")
        taxon = registro.get("taxon")
        arquivo = registro.get("arquivo")
        url = registro.get("url")
        if (
            grupo not in GRUPOS_INSETOS
            or not isinstance(autor, str)
            or not autor.strip()
            or not isinstance(licenca, str)
            or licenca.casefold() not in LICENCAS_PERMITIDAS
            or not isinstance(taxon, str)
            or not isinstance(arquivo, str)
            or not isinstance(url, str)
        ):
            descartados["licenca_nao_permitida"] += 1
            continue
        caminho = _resolver_arquivo_interno(raiz, arquivo)
        try:
            with Image.open(caminho) as imagem_aberta:
                if imagem_aberta.width * imagem_aberta.height > LIMITE_PIXELS_IMAGEM:
                    raise ValueError("A foto excede o limite de pixels permitido.")
                imagem_aberta.load()
                imagem = imagem_aberta.convert("RGB")
            mascara_rembg = remove(imagem, session=sessao, only_mask=True)
            mascara = _maior_componente_conectado(mascara_rembg)
        except Exception:
            descartados["falha_segmentacao"] += 1
            continue
        caixa = mascara.getbbox()
        if caixa is None:
            descartados["mascara_vazia"] += 1
            continue
        mascara_recortada = mascara.crop(caixa)
        imagem_recortada = imagem.crop(caixa)
        fundo = _cor_fundo_borda(imagem)
        if _borda_parece_fundo(imagem_recortada, mascara_recortada, fundo):
            descartados["fundo_residual"] += 1
            continue
        area = mascara_recortada.histogram()[255]
        if area < configuracao.area_minima_pixels:
            descartados["area_minima"] += 1
            continue
        pontos = _pontos_contorno_mascara(mascara_recortada)
        perimetro_casco = _perimetro_casco_convexo(pontos)
        perimetro_mascara = _perimetro_mascara(mascara_recortada)
        if (
            perimetro_casco == 0
            or perimetro_mascara / perimetro_casco > configuracao.limite_serrilhado
        ):
            descartados["bordas_serrilhadas"] += 1
            continue

        sprite = Image.new("RGBA", imagem_recortada.size, (0, 0, 0, 0))
        sprite.paste(imagem_recortada.convert("RGBA"), (0, 0), mascara_recortada)
        assinatura = _assinatura_sprite(sprite)
        if assinatura in assinaturas:
            descartados["duplicado"] += 1
            continue
        assinaturas.add(assinatura)
        id_observacao = registro.get("id_observacao")
        sprites.append(
            SpritePreparado(
                imagem=sprite,
                area=area,
                grupo=cast(GrupoInseto, grupo),
                autor=autor.strip(),
                fonte=f"https://www.inaturalist.org/observations/{id_observacao}",
                licenca=licenca.casefold(),
                especie=taxon,
                fragmentado=False,
                indice_origem=indice,
                url_foto=url,
            )
        )
    return sprites, len(fotos)


def _maior_componente_conectado(mascara: Image.Image) -> Image.Image:
    """Mantém o maior componente 8-conectado de uma máscara de segmentação."""
    mascara_binaria = mascara.convert("L").point(
        lambda valor: 255 if valor >= 128 else 0
    )
    largura, altura = mascara_binaria.size
    pixels = mascara_binaria.tobytes()
    pais: list[int] = []
    tamanhos: list[int] = []
    linhas: list[list[tuple[int, int, int]]] = []

    def encontrar(identificador: int) -> int:
        while pais[identificador] != identificador:
            pais[identificador] = pais[pais[identificador]]
            identificador = pais[identificador]
        return identificador

    def unir(primeiro: int, segundo: int) -> None:
        raiz_a = encontrar(primeiro)
        raiz_b = encontrar(segundo)
        if raiz_a == raiz_b:
            return
        if tamanhos[raiz_a] < tamanhos[raiz_b]:
            raiz_a, raiz_b = raiz_b, raiz_a
        pais[raiz_b] = raiz_a
        tamanhos[raiz_a] += tamanhos[raiz_b]

    anterior: list[tuple[int, int, int]] = []
    for y in range(altura):
        inicio_linha = y * largura
        atual: list[tuple[int, int, int]] = []
        x = 0
        while x < largura:
            if pixels[inicio_linha + x] < 128:
                x += 1
                continue
            inicio = x
            while x < largura and pixels[inicio_linha + x] >= 128:
                x += 1
            fim = x - 1
            identificador = len(pais)
            pais.append(identificador)
            tamanhos.append(fim - inicio + 1)
            atual.append((inicio, fim, identificador))
        indice_anterior = 0
        for inicio, fim, identificador in atual:
            while (
                indice_anterior < len(anterior)
                and anterior[indice_anterior][1] < inicio - 1
            ):
                indice_anterior += 1
            indice = indice_anterior
            while indice < len(anterior) and anterior[indice][0] <= fim + 1:
                unir(identificador, anterior[indice][2])
                indice += 1
        linhas.append(atual)
        anterior = atual

    if not pais:
        return Image.new("L", mascara_binaria.size, 0)
    areas: Counter[int] = Counter()
    for identificador, tamanho in enumerate(tamanhos):
        areas[encontrar(identificador)] += tamanho
    maior = max(areas, key=areas.get)
    saida = bytearray(largura * altura)
    for y, runs in enumerate(linhas):
        inicio_linha = y * largura
        for inicio, fim, identificador in runs:
            if encontrar(identificador) == maior:
                saida[inicio_linha + inicio : inicio_linha + fim + 1] = b"\xff" * (
                    fim - inicio + 1
                )
    return Image.frombytes("L", (largura, altura), bytes(saida))


def _pontos_contorno_mascara(mascara: Image.Image) -> list[tuple[int, int]]:
    largura, altura = mascara.size
    pixels = mascara.tobytes()
    pontos: list[tuple[int, int]] = []
    for y in range(altura):
        for x in range(largura):
            indice = y * largura + x
            if pixels[indice] < 128:
                continue
            if (
                x == 0
                or y == 0
                or x == largura - 1
                or y == altura - 1
                or pixels[indice - 1] < 128
                or pixels[indice + 1] < 128
                or pixels[indice - largura] < 128
                or pixels[indice + largura] < 128
            ):
                pontos.append((x, y))
    return pontos


def _cor_fundo_borda(imagem: Image.Image) -> tuple[int, int, int]:
    largura, altura = imagem.size
    pixels = imagem.convert("RGB").load()
    cores = [
        pixels[x, y]
        for y in range(altura)
        for x in range(largura)
        if x == 0 or y == 0 or x == largura - 1 or y == altura - 1
    ]
    canais = tuple(
        int(sorted(cor[indice] for cor in cores)[len(cores) // 2])
        for indice in range(3)
    )
    return cast(tuple[int, int, int], canais)


def _borda_parece_fundo(
    imagem: Image.Image,
    mascara: Image.Image,
    cor_fundo: tuple[int, int, int],
) -> bool:
    largura, altura = imagem.size
    pixels_imagem = imagem.convert("RGB").load()
    pixels_mascara = mascara.convert("L").load()
    cores_borda = [
        pixels_imagem[x, y]
        for y in range(altura)
        for x in range(largura)
        if (x < 2 or y < 2 or x >= largura - 2 or y >= altura - 2)
        and pixels_mascara[x, y] >= 128
    ]
    if len(cores_borda) < 4:
        return False
    semelhantes = sum(
        math.dist(cor, cor_fundo) <= DISTANCIA_COR_FUNDO for cor in cores_borda
    )
    return semelhantes / len(cores_borda) >= LIMITE_FRACAO_BORDA_FUNDO


def _normalizar_nome(nome: str | None) -> str:
    texto = unicodedata.normalize("NFKD", nome or "")
    return "".join(
        caractere for caractere in texto if not unicodedata.combining(caractere)
    ).casefold()


def _inferir_grupo(nome: str | None) -> str | None:
    texto = _normalizar_nome(nome)
    regras = (
        ("mosca", ("musca", "calliphoridae", "drosophila", "mosca")),
        ("mosquito", ("culex", "aedes", "mosquito")),
        ("formiga", ("formicidae", "formiga", "ant")),
        ("barata", ("blattodea", "barata", "cockroach")),
        ("mariposa", ("lepidoptera", "mariposa", "moth")),
        ("besouro", ("coleoptera", "besouro", "beetle")),
    )
    return next(
        (grupo for grupo, termos in regras if any(termo in texto for termo in termos)),
        None,
    )


def _perimetro_mascara(mascara: Image.Image) -> int:
    return _perimetro_horizontal(mascara) + _perimetro_horizontal(
        mascara.transpose(Image.Transpose.TRANSPOSE)
    )


def _perimetro_horizontal(mascara: Image.Image) -> int:
    largura, altura = mascara.size
    pixels = mascara.tobytes()
    perimetro = 0
    for y in range(altura):
        linha = pixels[y * largura : (y + 1) * largura]
        if not linha:
            continue
        perimetro += int(linha[0] != 0) + int(linha[-1] != 0)
        perimetro += sum(
            esquerda != direita for esquerda, direita in zip(linha, linha[1:])
        )
    return perimetro


def _perimetro_casco_convexo(pontos: list[tuple[int, int]]) -> float:
    pontos_unicos = sorted(set(pontos))
    if len(pontos_unicos) < 2:
        return 0.0

    def produto_vetorial(
        origem: tuple[int, int],
        primeiro: tuple[int, int],
        segundo: tuple[int, int],
    ) -> int:
        return (primeiro[0] - origem[0]) * (segundo[1] - origem[1]) - (
            primeiro[1] - origem[1]
        ) * (segundo[0] - origem[0])

    inferior: list[tuple[int, int]] = []
    for ponto in pontos_unicos:
        while (
            len(inferior) >= 2
            and produto_vetorial(inferior[-2], inferior[-1], ponto) <= 0
        ):
            inferior.pop()
        inferior.append(ponto)

    superior: list[tuple[int, int]] = []
    for ponto in reversed(pontos_unicos):
        while (
            len(superior) >= 2
            and produto_vetorial(superior[-2], superior[-1], ponto) <= 0
        ):
            superior.pop()
        superior.append(ponto)

    casco = inferior[:-1] + superior[:-1]
    if len(casco) < 2:
        return 0.0
    return sum(
        math.dist(casco[indice], casco[(indice + 1) % len(casco)])
        for indice in range(len(casco))
    )


def _gerar_fragmentos(
    sprites: list[SpritePreparado],
    configuracao: ConfiguracaoPreparo,
    descartados: Counter[str],
) -> list[SpritePreparado]:
    if not sprites:
        return []
    rng = random.Random(configuracao.semente)
    quantidade = max(1, round(len(sprites) * configuracao.fracao_fragmentos))
    quantidade = min(quantidade, len(sprites))
    minimo_area = math.ceil(configuracao.area_minima_pixels / 2)
    fragmentos: list[SpritePreparado] = []
    hashes = {_assinatura_sprite(sprite.imagem) for sprite in sprites}
    for sprite in rng.sample(sprites, quantidade):
        imagem_fragmento = _recortar_fragmento(sprite.imagem, rng, minimo_area)
        if imagem_fragmento is None:
            continue
        assinatura = _assinatura_sprite(imagem_fragmento)
        if assinatura in hashes:
            descartados["duplicado"] += 1
            continue
        hashes.add(assinatura)
        fragmentos.append(
            SpritePreparado(
                imagem=imagem_fragmento,
                area=imagem_fragmento.getchannel("A").histogram()[255],
                grupo=sprite.grupo,
                autor=sprite.autor,
                fonte=sprite.fonte,
                licenca=sprite.licenca,
                especie=sprite.especie,
                fragmentado=True,
                indice_origem=sprite.indice_origem,
                url_foto=sprite.url_foto,
            )
        )
    return fragmentos


def _recortar_fragmento(
    imagem: Image.Image,
    rng: random.Random,
    area_minima: int,
) -> Image.Image | None:
    largura, altura = imagem.size
    for _ in range(100):
        largura_corte = max(1, round(largura * rng.uniform(0.45, 0.9)))
        altura_corte = max(1, round(altura * rng.uniform(0.45, 0.9)))
        if largura > 1:
            largura_corte = min(largura - 1, largura_corte)
        if altura > 1:
            altura_corte = min(altura - 1, altura_corte)
        esquerda = rng.randint(0, largura - largura_corte)
        superior = rng.randint(0, altura - altura_corte)
        fragmento = imagem.crop(
            (
                esquerda,
                superior,
                esquerda + largura_corte,
                superior + altura_corte,
            )
        )
        if fragmento.getchannel("A").histogram()[255] >= area_minima:
            return fragmento
    return None


def _assinatura_sprite(imagem: Image.Image) -> str:
    return hashlib.sha256(
        imagem.width.to_bytes(4, "big")
        + imagem.height.to_bytes(4, "big")
        + imagem.tobytes()
    ).hexdigest()


def _criar_manifesto(
    sprites: list[SpritePreparado],
    inteiros: list[SpritePreparado],
) -> tuple[list[dict[str, object]], dict[str, int], dict[str, int]]:
    ordenados = sorted(
        sprites,
        key=lambda sprite: (sprite.area, sprite.indice_origem, sprite.fragmentado),
    )
    inteiros_ordenados = sorted(
        inteiros,
        key=lambda sprite: (sprite.area, sprite.indice_origem),
    )
    categorias_por_origem: dict[int, CategoriaSprite] = {}
    quantidade_inteiros = len(inteiros_ordenados)
    for indice, sprite in enumerate(inteiros_ordenados):
        indice_tercil = min(2, (indice * 3) // quantidade_inteiros)
        categorias_por_origem[sprite.indice_origem] = cast(
            CategoriaSprite, CATEGORIAS[indice_tercil]
        )

    contagens_categoria = {nome: 0 for nome in CATEGORIAS}
    contagens_grupo = {nome: 0 for nome in GRUPOS_INSETOS}
    manifesto: list[dict[str, object]] = []
    for indice, sprite in enumerate(ordenados):
        categoria = categorias_por_origem[sprite.indice_origem]
        contagens_categoria[categoria] += 1
        contagens_grupo[sprite.grupo] += 1
        registro: dict[str, object] = {
            "arquivo": f"insetos/sprite_{indice + 1:06d}.png",
            "categoria": categoria,
            "grupo": sprite.grupo,
            "autor": sprite.autor,
            "fonte": sprite.fonte,
            "licenca": sprite.licenca,
            "fragmentado": sprite.fragmentado,
        }
        if sprite.especie is not None:
            registro["especie"] = sprite.especie
        if sprite.url_foto is not None:
            registro["url_foto"] = sprite.url_foto
        manifesto.append(registro)
    return manifesto, contagens_categoria, contagens_grupo


def _publicar_banco(
    saida: Path,
    manifesto: list[dict[str, object]],
    relatorio: dict[str, object],
    sprites: list[SpritePreparado],
) -> None:
    saida.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".preparar-sprites-",
        dir=saida.parent,
    ) as diretorio_temporario:
        staging = Path(diretorio_temporario)
        pasta_insetos = staging / "insetos"
        pasta_insetos.mkdir()
        for registro, sprite in zip(
            manifesto,
            sorted(
                sprites,
                key=lambda item: (item.area, item.indice_origem, item.fragmentado),
            ),
            strict=True,
        ):
            sprite.imagem.save(
                staging / str(registro["arquivo"]),
                format="PNG",
                optimize=False,
            )
        (staging / "manifest.json").write_text(
            json.dumps(
                {"sprites": manifesto}, ensure_ascii=False, sort_keys=True, indent=2
            )
            + "\n",
            encoding="utf-8",
        )
        (staging / "relatorio.json").write_text(
            json.dumps(relatorio, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        if saida.exists():
            if not saida.is_dir() or any(saida.iterdir()):
                raise FileExistsError(f"O diretório de saída não está vazio: {saida}.")
            saida.rmdir()
        staging.rename(saida)


def criar_parser() -> argparse.ArgumentParser:
    """Cria a interface para converter COCO ou fotos coletadas do iNaturalist.

    Returns:
        Parser com caminhos, procedência, semente e limiares de qualidade.
    """
    parser = argparse.ArgumentParser(
        description="Prepara sprites RGBA a partir de COCO ou fotos do iNaturalist."
    )
    parser.add_argument(
        "--entrada",
        type=Path,
        required=True,
        help="Raiz externa dos dados ou diretório COCO local.",
    )
    parser.add_argument(
        "--saida", type=Path, required=True, help="Diretório novo ou vazio."
    )
    parser.add_argument(
        "--fonte", default="", help="Identificação pública da fonte COCO."
    )
    parser.add_argument(
        "--licenca", default="", help="Licença identificada do conjunto COCO."
    )
    parser.add_argument(
        "--semente", type=int, required=True, help="Semente de fragmentação."
    )
    parser.add_argument(
        "--anotacoes",
        type=Path,
        help="JSON COCO relativo à entrada; omita quando houver um único JSON na raiz.",
    )
    parser.add_argument(
        "--area-minima-pixels",
        type=int,
        default=AREA_MINIMA_PIXELS,
        help=f"Área opaca mínima (padrão: {AREA_MINIMA_PIXELS}).",
    )
    parser.add_argument(
        "--limite-serrilhado",
        type=float,
        default=LIMITE_RAZAO_SERRILHADO,
        help=f"Razão máxima perímetro/casco convexo (padrão: {LIMITE_RAZAO_SERRILHADO}).",
    )
    parser.add_argument(
        "--fracao-fragmentos",
        type=float,
        default=FRACAO_FRAGMENTOS,
        help=f"Fração de sprites inteiros a recortar (padrão: {FRACAO_FRAGMENTOS}).",
    )
    parser.add_argument(
        "--grupo-coco",
        choices=GRUPOS_INSETOS,
        help="Grupo usado se a categoria COCO não identificar o táxon.",
    )
    return parser


def main(argumentos: list[str] | None = None) -> int:
    """Executa a conversão local e retorna um status de processo.

    Args:
        argumentos: Argumentos explícitos; usa `sys.argv` quando ausente.

    Returns:
        Zero após publicar o banco; dois para uma entrada ou configuração inválida.
    """
    parser = criar_parser()
    opcoes = parser.parse_args(argumentos)
    try:
        dados_externos = diretorio_dados_configurado()
        entrada = opcoes.entrada.resolve()
        saida = opcoes.saida.resolve()
        if not entrada.is_relative_to(dados_externos):
            raise ValueError("A entrada precisa ficar em TRAPSIGHT_TRAINING_DATA_DIR.")
        if not saida.is_relative_to(dados_externos):
            raise ValueError("A saída precisa ficar em TRAPSIGHT_TRAINING_DATA_DIR.")
        configuracao = ConfiguracaoPreparo(
            entrada=entrada,
            saida=saida,
            fonte=opcoes.fonte,
            licenca=opcoes.licenca,
            semente=opcoes.semente,
            anotacoes=opcoes.anotacoes,
            area_minima_pixels=opcoes.area_minima_pixels,
            limite_serrilhado=opcoes.limite_serrilhado,
            fracao_fragmentos=opcoes.fracao_fragmentos,
            grupo_coco=opcoes.grupo_coco,
        )
        relatorio = prepare_sprite_bank(configuracao)
    except (OSError, ValueError) as erro:
        parser.error(str(erro))
        return 2

    print(f"Banco preparado: {relatorio['sprites_aceitos']} sprites.")
    print(f"Fragmentos: {relatorio['numero_fragmentos']}.")
    print(f"Semente: {opcoes.semente}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
