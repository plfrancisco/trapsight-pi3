"""Converte sprites públicos em um catálogo físico reutilizável pelo gerador."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from PIL import Image

PIXELS_POR_MM_SCAN_1200_DPI = 47.24
LIMIAR_MOSCA_MOSQUITO_MM = 2.0
LIMIAR_FORMIGA_VESPA_MM = 3.0
FONTE_AMAZONIA_PADRAO = "https://doi.org/10.6084/m9.figshare.28688198"
LICENCA_AMAZONIA_PADRAO = "CC BY 4.0"
AUTOR_AMAZONIA_PADRAO = "Lucas F. Colares; Carlos A. Peres; Cristian S. Dambros"
CLASSE_UMS_EQUIVALENTE = {
    "Brachycera": "Diptera",
    "Nematocera": "Diptera",
    "Coleoptera": "Coleoptera",
    "Hemiptera": "Hemiptera",
    "Hymenoptera": "Hymenoptera",
    "Isoptera": "Isoptera",
    "Lepidoptera": "Lepidoptera",
}
CLASSE_AMAZONIA_GRUPO = {
    "Araneae": "outro",
    "Brachycera": "mosca",
    "Coleoptera": "besouro",
    "Ephemeroptera": "outro",
    "Hemiptera": "percevejo",
    "Isoptera": "cupim",
    "Lepidoptera": "mariposa",
    "Nematocera": "mosquito",
    "Odonata": "outro",
    "Orthoptera": "outro",
    "Trichoptera": "outro",
}


def converter_catalogo(
    diretorio_ums: Path,
    manifesto_ums: Path,
    metadados_ums: Path,
    diretorio_amazonia: Path,
    manifesto_amazonia: Path,
    saida: Path,
    semente: int,
    fonte_amazonia: str,
    licenca_amazonia: str,
    autor_amazonia: str,
) -> dict[str, Any]:
    """Cria um catálogo novo, copiando PNGs apenas para fora do repositório."""
    fonte_ums, licenca_ums, autor_ums = _ler_procedencia_ums(metadados_ums)
    _validar_procedencia(fonte_amazonia, licenca_amazonia, autor_amazonia)
    if licenca_amazonia.strip().casefold() not in {"cc by 4.0", "cc-by-4.0"}:
        raise ValueError("A licença do catálogo Amazônia precisa ser CC BY 4.0.")

    registros_ums = _ler_lista(manifesto_ums, "sprites UMS")
    registros_amazonia = _ler_lista(manifesto_amazonia, "sprites da Amazônia")
    tamanhos_ums = [_tamanho_real_ums(registro) for registro in registros_ums]
    if not tamanhos_ums:
        raise ValueError("O manifesto UMS não contém sprites com escala física.")
    limites = (_quantil(tamanhos_ums, 1 / 3), _quantil(tamanhos_ums, 2 / 3))
    tamanhos_por_classe: dict[str, list[float]] = defaultdict(list)
    for registro, tamanho in zip(registros_ums, tamanhos_ums, strict=True):
        classe = _campo_texto(registro, "classe", "manifesto UMS")
        tamanhos_por_classe[classe].append(tamanho)

    raiz_saida = saida.resolve()
    if raiz_saida.exists() and any(raiz_saida.iterdir()):
        raise FileExistsError(f"O diretório de saída não está vazio: {raiz_saida}.")
    raiz_saida.mkdir(parents=True, exist_ok=True)
    pastas = {"ums": raiz_saida / "ums", "amazonia": raiz_saida / "amazonia"}
    for pasta in pastas.values():
        pasta.mkdir(exist_ok=True)

    sprites: list[dict[str, Any]] = []
    contagem_grupos: Counter[str] = Counter()
    contagem_categorias: Counter[str] = Counter()
    for registro, tamanho_mm in zip(registros_ums, tamanhos_ums, strict=True):
        classe = _campo_texto(registro, "classe", "manifesto UMS")
        identificador = _campo_texto(registro, "id", "manifesto UMS")
        sprite = _criar_registro(
            registro=registro,
            identificador=identificador,
            classe=classe,
            tamanho_mm=tamanho_mm,
            px_por_mm=PIXELS_POR_MM_SCAN_1200_DPI
            * _numero_positivo(registro, "escala"),
            origem_escala="medida",
            pasta_origem=diretorio_ums / "png",
            pasta_destino=pastas["ums"],
            prefixo="ums",
            autor=autor_ums,
            fonte=fonte_ums,
            licenca=licenca_ums,
            limites=limites,
            grupo=_grupo_ums(classe, tamanho_mm),
        )
        sprites.append(sprite)
        contagem_grupos[sprite["grupo"]] += 1
        contagem_categorias[sprite["categoria"]] += 1

    for indice, registro in enumerate(registros_amazonia):
        classe = _campo_texto(registro, "classe", "manifesto da Amazônia")
        identificador = _campo_texto(registro, "id", "manifesto da Amazônia")
        classe_ums = CLASSE_UMS_EQUIVALENTE.get(classe)
        distribuicao = tamanhos_por_classe.get(classe_ums or "", tamanhos_ums)
        tamanho_mm = random.Random(_semente_identificador(semente, identificador)).choice(
            distribuicao
        )
        grupo = CLASSE_AMAZONIA_GRUPO.get(classe)
        if grupo is None:
            grupo = _grupo_ums(classe_ums or "Rara", tamanho_mm)
        elif classe == "Hymenoptera":
            grupo = _grupo_himenoptero(tamanho_mm)
        sprite = _criar_registro(
            registro=registro,
            identificador=identificador,
            classe=classe,
            tamanho_mm=tamanho_mm,
            px_por_mm=None,
            origem_escala="estimada_por_grupo_ums",
            pasta_origem=diretorio_amazonia / "png",
            pasta_destino=pastas["amazonia"],
            prefixo="amazonia",
            autor=autor_amazonia,
            fonte=fonte_amazonia,
            licenca=licenca_amazonia,
            limites=limites,
            grupo=grupo,
        )
        sprites.append(sprite)
        contagem_grupos[sprite["grupo"]] += 1
        contagem_categorias[sprite["categoria"]] += 1

    manifesto = {
        "versao": 2,
        "semente_estimativa_amazonia": semente,
        "limites_categoria_mm": {"pequeno_ate": limites[0], "medio_ate": limites[1]},
        "regra_tamanho_ums": "max(largura, altura) / (47.24 * escala)",
        "regra_tamanho_amazonia": "amostrado da distribuição UMS da classe equivalente",
        "sprites": sprites,
    }
    (raiz_saida / "manifest.json").write_text(
        json.dumps(manifesto, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    (raiz_saida / "resumo.json").write_text(
        json.dumps(
            {
                "total": len(sprites),
                "por_grupo": dict(sorted(contagem_grupos.items())),
                "por_categoria": dict(sorted(contagem_categorias.items())),
                "fontes": [
                    {"autor": autor_ums, "fonte": fonte_ums, "licenca": licenca_ums},
                    {
                        "autor": autor_amazonia,
                        "fonte": fonte_amazonia,
                        "licenca": licenca_amazonia,
                    },
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return manifesto


def _criar_registro(
    *,
    registro: dict[str, Any],
    identificador: str,
    classe: str,
    tamanho_mm: float,
    px_por_mm: float | None,
    origem_escala: str,
    pasta_origem: Path,
    pasta_destino: Path,
    prefixo: str,
    autor: str,
    fonte: str,
    licenca: str,
    limites: tuple[float, float],
    grupo: str,
) -> dict[str, Any]:
    _validar_procedencia(fonte, licenca, autor)
    if not identificador or Path(identificador).name != identificador:
        raise ValueError(f"Identificador de sprite inválido: {identificador!r}.")
    origem = pasta_origem / f"{identificador}.png"
    destino = pasta_destino / f"{identificador}.png"
    if not origem.is_file():
        raise FileNotFoundError(f"PNG do sprite não encontrado: {origem}.")
    with Image.open(origem) as imagem:
        if imagem.format != "PNG" or "A" not in imagem.getbands():
            raise ValueError(f"O sprite precisa ser um PNG RGBA: {origem}.")
        if imagem.width < 1 or imagem.height < 1:
            raise ValueError(f"O sprite está vazio: {origem}.")
    if destino.exists():
        raise ValueError(f"Dois sprites usam o mesmo identificador: {destino.name}.")
    shutil.copyfile(origem, destino)
    return {
        "arquivo": f"{prefixo}/{identificador}.png",
        "categoria": _categoria(tamanho_mm, limites),
        "grupo": grupo,
        "autor": autor,
        "fonte": fonte,
        "licenca": licenca,
        "especie": None,
        "fragmentado": False,
        "tamanho_mm": round(tamanho_mm, 6),
        "px_por_mm": round(px_por_mm, 6) if px_por_mm is not None else None,
        "origem_escala": origem_escala,
        "classe_origem": classe,
        "origem": prefixo,
        "id_origem": identificador,
        "area_px_origem": registro.get("area_px"),
    }


def _ler_procedencia_ums(caminho: Path) -> tuple[str, str, str]:
    try:
        meta = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as erro:
        raise ValueError(f"Não foi possível ler a procedência UMS em {caminho}.") from erro
    licenca = meta.get("license", {}).get("name") if isinstance(meta, dict) else None
    doi = meta.get("doi") if isinstance(meta, dict) else None
    autores = meta.get("authors", []) if isinstance(meta, dict) else []
    nomes = [
        autor.get("full_name")
        for autor in autores
        if isinstance(autor, dict) and autor.get("full_name")
    ]
    fonte = f"https://doi.org/{doi}" if isinstance(doi, str) and doi else ""
    autor = "; ".join(nomes)
    _validar_procedencia(fonte, licenca, autor)
    if licenca.casefold() not in {"cc by 4.0", "cc-by-4.0"}:
        raise ValueError("A licença registrada para UMS precisa ser CC BY 4.0.")
    return fonte, "CC-BY-4.0", autor


def _validar_procedencia(fonte: str, licenca: str, autor: str) -> None:
    if not fonte.strip():
        raise ValueError("A fonte pública do conjunto de sprites é obrigatória.")
    if not licenca.strip():
        raise ValueError("A licença do conjunto de sprites é obrigatória.")
    if not autor.strip():
        raise ValueError("A autoria do conjunto de sprites é obrigatória.")


def _ler_lista(caminho: Path, nome: str) -> list[dict[str, Any]]:
    try:
        registros = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as erro:
        raise ValueError(f"Não foi possível ler o {nome} em {caminho}.") from erro
    if not isinstance(registros, list) or any(
        not isinstance(registro, dict) for registro in registros
    ):
        raise ValueError(f"O {nome} precisa ser uma lista de objetos JSON.")
    return registros


def _campo_texto(registro: dict[str, Any], campo: str, origem: str) -> str:
    valor = registro.get(campo)
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"O campo '{campo}' é obrigatório em {origem}.")
    return valor.strip()


def _numero_positivo(registro: dict[str, Any], campo: str) -> float:
    valor = registro.get(campo)
    if (
        isinstance(valor, bool)
        or not isinstance(valor, (int, float))
        or not math.isfinite(valor)
        or valor <= 0
    ):
        raise ValueError(f"O campo '{campo}' precisa ser um número positivo.")
    return float(valor)


def _tamanho_real_ums(registro: dict[str, Any]) -> float:
    largura = _numero_positivo(registro, "largura")
    altura = _numero_positivo(registro, "altura")
    escala = _numero_positivo(registro, "escala")
    return max(largura, altura) / (PIXELS_POR_MM_SCAN_1200_DPI * escala)


def _grupo_ums(classe: str, tamanho_mm: float) -> str:
    if classe == "Diptera":
        return "mosquito" if tamanho_mm <= LIMIAR_MOSCA_MOSQUITO_MM else "mosca"
    if classe == "Hymenoptera":
        return _grupo_himenoptero(tamanho_mm)
    return {
        "Blattodea": "barata",
        "Coleoptera": "besouro",
        "Hemiptera": "percevejo",
        "Isoptera": "cupim",
        "Lepidoptera": "mariposa",
        "Psocoptera": "psocoptero",
    }.get(classe, "outro")


def _grupo_himenoptero(tamanho_mm: float) -> str:
    return "formiga" if tamanho_mm <= LIMIAR_FORMIGA_VESPA_MM else "vespa"


def _categoria(tamanho_mm: float, limites: tuple[float, float]) -> str:
    if tamanho_mm <= limites[0]:
        return "pequeno"
    if tamanho_mm <= limites[1]:
        return "medio"
    return "grande"


def _quantil(valores: list[float], proporcao: float) -> float:
    ordenados = sorted(valores)
    posicao = (len(ordenados) - 1) * proporcao
    inferior = math.floor(posicao)
    superior = math.ceil(posicao)
    if inferior == superior:
        return ordenados[inferior]
    fracao = posicao - inferior
    return ordenados[inferior] * (1 - fracao) + ordenados[superior] * fracao


def _semente_identificador(semente: int, identificador: str) -> int:
    digest = hashlib.sha256(f"{semente}:{identificador}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def criar_parser() -> argparse.ArgumentParser:
    """Configura caminhos de origem, atribuição e saída do catálogo."""
    parser = argparse.ArgumentParser(
        description="Importa sprites reais com tamanho físico e atribuição de licença."
    )
    parser.add_argument(
        "--ums-sprites",
        type=Path,
        default=Path(r"D:\dados\trapsight\sprites-ums"),
    )
    parser.add_argument(
        "--ums-meta",
        type=Path,
        default=Path(r"D:\dados\trapsight\dataset-real-ums\meta.json"),
    )
    parser.add_argument(
        "--amazonia-sprites",
        type=Path,
        default=Path(r"D:\dados\trapsight\sprites-amazonia"),
    )
    parser.add_argument(
        "--saida",
        type=Path,
        default=Path(r"D:\dados\trapsight\sprites-reais"),
    )
    parser.add_argument("--semente", type=int, default=20261021)
    parser.add_argument("--amazonia-fonte", required=True)
    parser.add_argument("--amazonia-licenca", required=True)
    parser.add_argument("--amazonia-autor", required=True)
    return parser


def main(argumentos: list[str] | None = None) -> int:
    """Valida as fontes e grava um catálogo pronto para o gerador."""
    parser = criar_parser()
    opcoes = parser.parse_args(argumentos)
    try:
        manifesto = converter_catalogo(
            diretorio_ums=opcoes.ums_sprites,
            manifesto_ums=opcoes.ums_sprites / "meta.json",
            metadados_ums=opcoes.ums_meta,
            diretorio_amazonia=opcoes.amazonia_sprites,
            manifesto_amazonia=opcoes.amazonia_sprites / "meta_filtrado.json",
            saida=opcoes.saida,
            semente=opcoes.semente,
            fonte_amazonia=opcoes.amazonia_fonte,
            licenca_amazonia=opcoes.amazonia_licenca,
            autor_amazonia=opcoes.amazonia_autor,
        )
    except (OSError, ValueError) as erro:
        parser.error(str(erro))
        return 2
    grupos = Counter(registro["grupo"] for registro in manifesto["sprites"])
    print(f"Catálogo criado: {opcoes.saida.resolve()}")
    print(f"Sprites: {len(manifesto['sprites'])}")
    print(f"Grupos: {dict(sorted(grupos.items()))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
