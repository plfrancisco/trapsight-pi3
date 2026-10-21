"""Coleta fotos de insetos brasileiros com licença aberta do iNaturalist."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from PIL import Image

PLACE_ID_BRASIL = 6878
LICENCAS_PERMITIDAS = frozenset({"cc0", "cc-by", "cc-by-nc"})
FOTOS_POR_GRUPO = 60
FOTOS_POR_PAGINA = 200
INTERVALO_REQUISICOES_SEGUNDOS = 1.0
LIMITE_BYTES_FOTO = 30_000_000
LIMITE_PIXELS_IMAGEM = 40_000_000
GRUPOS_TAXONS: dict[str, tuple[str, ...]] = {
    "mosca": ("Musca domestica", "Calliphoridae", "Drosophila"),
    "mosquito": ("Culex", "Aedes"),
    "formiga": ("Formicidae",),
    "barata": ("Blattodea",),
    "mariposa": ("Lepidoptera",),
    "besouro": ("Coleoptera",),
}
EXTENSOES_IMAGEM = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}
HOSTS_FOTOS_PERMITIDOS = {
    "inaturalist-open-data.s3.amazonaws.com",
    "static.inaturalist.org",
}


@dataclass(frozen=True)
class ConfiguracaoColeta:
    """Define a meta e o local externo usados para coletar as fotos."""

    diretorio_dados: Path
    fotos_por_grupo: int = FOTOS_POR_GRUPO
    paginas_por_taxon: int = 40
    semente: int = 20261021

    def __post_init__(self) -> None:
        if self.fotos_por_grupo < 1:
            raise ValueError("A meta de fotos por grupo precisa ser positiva.")
        if self.paginas_por_taxon < 1:
            raise ValueError("O limite de páginas precisa ser positivo.")
        if not self.diretorio_dados.is_absolute():
            raise ValueError("O diretório de dados precisa ser absoluto.")


class ClienteColeta(Protocol):
    """Contrato mínimo para acesso HTTP e testes isolados da rede."""

    def obter_json(self, url: str) -> object: ...

    def baixar(self, url: str) -> bytes: ...


class ClienteINaturalist:
    """Cliente público com cache local e limitação global de requisições."""

    def __init__(self, diretorio_cache: Path, diretorio_fotos: Path) -> None:
        self.diretorio_cache = diretorio_cache
        self.diretorio_fotos = diretorio_fotos
        self.diretorio_cache.mkdir(parents=True, exist_ok=True)
        self.diretorio_fotos.mkdir(parents=True, exist_ok=True)
        self._ultima_requisicao = 0.0

    def obter_json(self, url: str) -> object:
        """Lê uma resposta JSON do cache ou consulta a API pública."""
        caminho_cache = self._caminho_cache(url, ".json")
        if caminho_cache.exists():
            return json.loads(caminho_cache.read_text(encoding="utf-8"))
        conteudo = self._requisitar(url)
        try:
            resposta = json.loads(conteudo.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as erro:
            raise ValueError("A API do iNaturalist retornou JSON inválido.") from erro
        caminho_cache.write_text(
            json.dumps(resposta, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        return resposta

    def baixar(self, url: str) -> bytes:
        """Baixa uma foto respeitando o limite de tamanho da resposta."""
        return self._requisitar(url, limite_bytes=LIMITE_BYTES_FOTO)

    def _requisitar(self, url: str, limite_bytes: int = 50_000_000) -> bytes:
        ultima_falha: Exception | None = None
        for tentativa in range(5):
            espera = INTERVALO_REQUISICOES_SEGUNDOS - (
                time.monotonic() - self._ultima_requisicao
            )
            if espera > 0:
                time.sleep(espera)
            requisicao = urllib.request.Request(
                url,
                headers={
                    "Accept": "application/json, image/*;q=0.9, */*;q=0.1",
                    "User-Agent": "TrapSightTrainingDataset/1.0",
                },
            )
            self._ultima_requisicao = time.monotonic()
            try:
                with urllib.request.urlopen(requisicao, timeout=60) as resposta:
                    conteudo = resposta.read(limite_bytes + 1)
                if len(conteudo) > limite_bytes:
                    raise ValueError("A resposta excede o limite de tamanho permitido.")
                return conteudo
            except urllib.error.HTTPError as erro:
                ultima_falha = erro
                if erro.code != 429 and not 500 <= erro.code < 600:
                    raise ValueError(
                        f"A requisição pública falhou com HTTP {erro.code}."
                    ) from erro
                retentativa = erro.headers.get("Retry-After")
                atraso = (
                    float(retentativa)
                    if retentativa and retentativa.isdigit()
                    else 2**tentativa
                )
                time.sleep(min(atraso, 60))
            except (urllib.error.URLError, TimeoutError) as erro:
                ultima_falha = erro
                time.sleep(min(2**tentativa, 60))
        raise ValueError(
            "A requisição pública falhou após cinco tentativas."
        ) from ultima_falha

    def _caminho_cache(self, url: str, extensao: str) -> Path:
        identificador = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return self.diretorio_cache / f"{identificador}{extensao}"


def coletar_fotos(
    configuracao: ConfiguracaoColeta,
    cliente: ClienteColeta | None = None,
) -> dict[str, object]:
    """Coleta fotos licenciadas, persiste procedência e permite retomada.

    Args:
        configuracao: Diretório externo e quantidade de fotos por grupo.
        cliente: Cliente HTTP substituível por um stub em testes.

    Returns:
        Resumo da coleta escrito também em `relatorio_coleta.json`.

    Raises:
        OSError: Se não for possível ler ou gravar dados locais.
        ValueError: Se a API ou os metadados não forem válidos ou a meta falhar.
    """
    raiz = configuracao.diretorio_dados.resolve()
    pasta_fotos = raiz / "inaturalist" / "fotos"
    pasta_cache = raiz / "inaturalist" / "cache" / "api"
    pasta_fotos.mkdir(parents=True, exist_ok=True)
    pasta_cache.mkdir(parents=True, exist_ok=True)
    caminho_manifesto = raiz / "inaturalist" / "manifesto_coleta.json"
    cliente = cliente or ClienteINaturalist(pasta_cache, pasta_fotos)
    registros = _carregar_registros_existentes(caminho_manifesto, raiz)
    por_grupo: dict[str, list[dict[str, object]]] = {
        grupo: [registro for registro in registros if registro["grupo"] == grupo]
        for grupo in GRUPOS_TAXONS
    }
    ids_fotos = {str(registro["id_foto"]) for registro in registros}
    descartes: Counter[str] = Counter()
    urls_taxons: dict[str, int] = {}
    rng = random.Random(configuracao.semente)

    for grupo, nomes_taxons in GRUPOS_TAXONS.items():
        meta_por_taxon = math.ceil(configuracao.fotos_por_grupo / len(nomes_taxons))
        for nome_taxon in nomes_taxons:
            fotos_do_taxon = [
                registro
                for registro in por_grupo[grupo]
                if registro.get("taxon") == nome_taxon
            ]
            if len(fotos_do_taxon) >= meta_por_taxon:
                continue
            id_taxon = _resolver_taxon(cliente, nome_taxon)
            urls_taxons[nome_taxon] = id_taxon
            for pagina in range(1, configuracao.paginas_por_taxon + 1):
                if len(fotos_do_taxon) >= meta_por_taxon:
                    break
                parametros = urllib.parse.urlencode(
                    {
                        "place_id": PLACE_ID_BRASIL,
                        "quality_grade": "research",
                        "taxon_id": id_taxon,
                        "photos": "true",
                        "per_page": FOTOS_POR_PAGINA,
                        "page": pagina,
                        "order": "desc",
                        "order_by": "created_at",
                    }
                )
                resposta = cliente.obter_json(
                    f"https://api.inaturalist.org/v1/observations?{parametros}"
                )
                observacoes = _extrair_resultados(resposta)
                if not observacoes:
                    break
                rng.shuffle(observacoes)
                for observacao in observacoes:
                    if len(fotos_do_taxon) >= meta_por_taxon:
                        break
                    selecionadas = _selecionar_fotos_observacao(
                        observacao,
                        grupo=grupo,
                        nome_taxon=nome_taxon,
                        ids_fotos=ids_fotos,
                        descartes=descartes,
                    )
                    for registro in selecionadas:
                        if len(fotos_do_taxon) >= meta_por_taxon:
                            break
                        url = str(registro["url"])
                        caminho_existente = _localizar_foto(pasta_fotos, registro)
                        if caminho_existente is None:
                            try:
                                conteudo = cliente.baixar(url)
                                extensao = _validar_foto(conteudo)
                            except (OSError, ValueError, urllib.error.URLError):
                                descartes["falha_download"] += 1
                                continue
                            destino = (
                                pasta_fotos / grupo / f"{registro['id_foto']}{extensao}"
                            )
                            destino.parent.mkdir(parents=True, exist_ok=True)
                            destino.write_bytes(conteudo)
                            caminho_existente = destino
                        registro["arquivo"] = caminho_existente.relative_to(
                            raiz
                        ).as_posix()
                        registro["taxon_id"] = id_taxon
                        por_grupo[grupo].append(registro)
                        fotos_do_taxon.append(registro)
                        ids_fotos.add(str(registro["id_foto"]))
                        registros.append(registro)
                        _gravar_manifesto(caminho_manifesto, configuracao, registros)

    for registros_grupo in por_grupo.values():
        rng.shuffle(registros_grupo)
    faltantes = {
        grupo: max(0, configuracao.fotos_por_grupo - len(fotos))
        for grupo, fotos in por_grupo.items()
    }
    relatorio = {
        "place_id": PLACE_ID_BRASIL,
        "quality_grade": "research",
        "licencas_permitidas": sorted(LICENCAS_PERMITIDAS),
        "tamanho_minimo_foto": "medium",
        "fotos_por_grupo_solicitadas": configuracao.fotos_por_grupo,
        "fotos_baixadas": len(registros),
        "fotos_por_grupo": {grupo: len(fotos) for grupo, fotos in por_grupo.items()},
        "fotos_por_taxon": {
            nome_taxon: sum(
                registro.get("taxon") == nome_taxon for registro in registros
            )
            for taxons in GRUPOS_TAXONS.values()
            for nome_taxon in taxons
        },
        "metas_nao_atingidas": faltantes,
        "taxons_resolvidos": urls_taxons,
        "descartados_por_motivo": dict(sorted(descartes.items())),
        "semente_selecao": configuracao.semente,
    }
    caminho_relatorio = caminho_manifesto.with_name("relatorio_coleta.json")
    _gravar_json(caminho_relatorio, relatorio)
    _gravar_manifesto(caminho_manifesto, configuracao, registros)
    if any(faltantes.values()):
        raise ValueError(
            "Meta de coleta não atingida; faltam fotos por grupo: "
            + ", ".join(
                f"{grupo}={quantidade}"
                for grupo, quantidade in faltantes.items()
                if quantidade
            )
        )
    return relatorio


def _resolver_taxon(cliente: ClienteColeta, nome: str) -> int:
    parametros = urllib.parse.urlencode({"q": nome, "per_page": 30})
    resposta = cliente.obter_json(
        f"https://api.inaturalist.org/v1/taxa/autocomplete?{parametros}"
    )
    resultados = resposta.get("results") if isinstance(resposta, dict) else resposta
    if not isinstance(resultados, list):
        raise ValueError(f"A resposta de busca do táxon {nome} é inválida.")
    correspondencias = [
        registro
        for registro in resultados
        if isinstance(registro, dict)
        and isinstance(registro.get("name"), str)
        and registro["name"].casefold() == nome.casefold()
    ]
    if not correspondencias or not isinstance(correspondencias[0].get("id"), int):
        raise ValueError(f"O táxon {nome} não foi encontrado no iNaturalist.")
    return correspondencias[0]["id"]


def _extrair_resultados(resposta: object) -> list[dict[str, object]]:
    if not isinstance(resposta, dict) or not isinstance(resposta.get("results"), list):
        raise ValueError("A resposta de observações do iNaturalist é inválida.")
    return [item for item in resposta["results"] if isinstance(item, dict)]


def _selecionar_fotos_observacao(
    observacao: dict[str, object],
    *,
    grupo: str,
    nome_taxon: str,
    ids_fotos: set[str],
    descartes: Counter[str],
) -> list[dict[str, object]]:
    fotos = observacao.get("photos")
    if not isinstance(fotos, list):
        descartes["observacao_sem_fotos"] += 1
        return []
    id_observacao = observacao.get("id")
    usuario = observacao.get("user")
    autor_observacao = (
        usuario.get("name") or usuario.get("login")
        if isinstance(usuario, dict)
        else None
    )
    registros: list[dict[str, object]] = []
    for foto in fotos:
        if not isinstance(foto, dict) or not _id_foto_valido(foto.get("id")):
            descartes["foto_sem_id"] += 1
            continue
        id_foto = str(foto["id"])
        if id_foto in ids_fotos:
            descartes["foto_duplicada"] += 1
            continue
        licenca = foto.get("license_code")
        if (
            not isinstance(licenca, str)
            or licenca.casefold() not in LICENCAS_PERMITIDAS
        ):
            descartes["licenca_nao_permitida"] += 1
            continue
        url = _url_tamanho_medio(foto)
        if url is None:
            descartes["sem_url_media"] += 1
            continue
        autor = foto.get("attribution") or autor_observacao
        if not isinstance(autor, str) or not autor.strip():
            descartes["autor_ausente"] += 1
            continue
        registros.append(
            {
                "id_observacao": id_observacao,
                "id_foto": id_foto,
                "url": url,
                "autor": autor.strip(),
                "licenca": licenca.casefold(),
                "taxon": nome_taxon,
                "grupo": grupo,
            }
        )
    return registros


def _url_tamanho_medio(foto: dict[str, object]) -> str | None:
    for campo in ("medium_url", "large_url", "original_url"):
        valor = foto.get(campo)
        if isinstance(valor, str) and _url_foto_permitida(valor):
            return valor
    urls = foto.get("urls")
    if isinstance(urls, dict):
        for chave in ("medium", "large", "original"):
            valor = urls.get(chave)
            if isinstance(valor, str) and _url_foto_permitida(valor):
                return valor
    valor = foto.get("url")
    if not isinstance(valor, str) or not _url_foto_permitida(valor):
        return None
    if "/square." in valor:
        return valor.replace("/square.", "/medium.", 1)
    if "/small." in valor:
        return valor.replace("/small.", "/medium.", 1)
    return valor


def _id_foto_valido(valor: object) -> bool:
    return (isinstance(valor, int) and not isinstance(valor, bool) and valor > 0) or (
        isinstance(valor, str) and valor.isdigit() and int(valor) > 0
    )


def _url_foto_permitida(url: str) -> bool:
    analisada = urllib.parse.urlparse(url)
    return (
        analisada.scheme == "https"
        and analisada.hostname in HOSTS_FOTOS_PERMITIDOS
        and analisada.username is None
        and analisada.password is None
        and analisada.port in (None, 443)
    )


def _validar_foto(conteudo: bytes) -> str:
    if not conteudo or len(conteudo) > LIMITE_BYTES_FOTO:
        raise ValueError("O conteúdo da foto está vazio ou excede o limite.")
    try:
        with Image.open(__import__("io").BytesIO(conteudo)) as imagem:
            if imagem.width * imagem.height > LIMITE_PIXELS_IMAGEM:
                raise ValueError("A foto excede o limite de resolução.")
            extensao = EXTENSOES_IMAGEM.get(imagem.format or "")
            if extensao is None:
                raise ValueError("O formato da foto não é aceito.")
            imagem.verify()
    except (OSError, Image.DecompressionBombError) as erro:
        raise ValueError("O conteúdo baixado não é uma imagem válida.") from erro
    return extensao


def _localizar_foto(
    pasta_fotos: Path,
    registro: dict[str, object],
) -> Path | None:
    id_foto = str(registro["id_foto"])
    grupo = str(registro["grupo"])
    candidatos = sorted((pasta_fotos / grupo).glob(f"{id_foto}.*"))
    return next((caminho for caminho in candidatos if caminho.is_file()), None)


def _carregar_registros_existentes(
    caminho: Path, raiz: Path
) -> list[dict[str, object]]:
    if not caminho.exists():
        return []
    try:
        manifesto = json.loads(caminho.read_text(encoding="utf-8"))
    except json.JSONDecodeError as erro:
        raise ValueError("O manifesto de coleta existente não é JSON válido.") from erro
    fotos = manifesto.get("fotos") if isinstance(manifesto, dict) else None
    if not isinstance(fotos, list):
        raise ValueError("O manifesto de coleta precisa conter uma lista 'fotos'.")
    registros: list[dict[str, object]] = []
    for registro in fotos:
        if not isinstance(registro, dict):
            continue
        grupo = registro.get("grupo")
        arquivo = registro.get("arquivo")
        id_foto = registro.get("id_foto")
        if grupo not in GRUPOS_TAXONS or not isinstance(arquivo, str):
            continue
        caminho_foto = (raiz / arquivo).resolve()
        if caminho_foto.is_relative_to(raiz) and caminho_foto.is_file() and id_foto:
            registros.append(dict(registro))
    return registros


def _gravar_manifesto(
    caminho: Path,
    configuracao: ConfiguracaoColeta,
    fotos: list[dict[str, object]],
) -> None:
    manifesto = {
        "place_id": PLACE_ID_BRASIL,
        "quality_grade": "research",
        "licencas_permitidas": sorted(LICENCAS_PERMITIDAS),
        "tamanho_minimo_foto": "medium",
        "meta_por_grupo": configuracao.fotos_por_grupo,
        "fotos": fotos,
    }
    _gravar_json(caminho, manifesto)


def _gravar_json(caminho: Path, dados: object) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(caminho.suffix + ".tmp")
    temporario.write_text(
        json.dumps(dados, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    temporario.replace(caminho)


def diretorio_dados_configurado() -> Path:
    """Resolve o diretório externo sem aceitar a raiz versionada do backend."""
    valor = os.environ.get("TRAPSIGHT_TRAINING_DATA_DIR")
    if not valor or not valor.strip():
        raise ValueError("Defina TRAPSIGHT_TRAINING_DATA_DIR fora do repositório.")
    caminho = Path(valor).expanduser()
    if not caminho.is_absolute():
        raise ValueError("TRAPSIGHT_TRAINING_DATA_DIR precisa ser absoluto.")
    raiz_repo = Path(__file__).resolve().parents[2]
    resolvido = caminho.resolve()
    if resolvido == raiz_repo or raiz_repo in resolvido.parents:
        raise ValueError("Os dados de treino não podem ficar no repositório.")
    return resolvido


def criar_parser() -> argparse.ArgumentParser:
    """Cria a interface para a coleta sem credenciais de API."""
    parser = argparse.ArgumentParser(
        description="Coleta fotos abertas de insetos brasileiros do iNaturalist."
    )
    parser.add_argument(
        "--fotos-por-grupo",
        type=int,
        default=FOTOS_POR_GRUPO,
        help=f"Meta de fotos únicas por grupo (padrão: {FOTOS_POR_GRUPO}).",
    )
    parser.add_argument("--semente", type=int, default=20261021)
    parser.add_argument("--paginas-por-taxon", type=int, default=40)
    return parser


def main(argumentos: list[str] | None = None) -> int:
    """Executa a coleta no diretório de dados configurado no ambiente."""
    parser = criar_parser()
    opcoes = parser.parse_args(argumentos)
    try:
        diretorio = diretorio_dados_configurado()
        relatorio = coletar_fotos(
            ConfiguracaoColeta(
                diretorio_dados=diretorio,
                fotos_por_grupo=opcoes.fotos_por_grupo,
                paginas_por_taxon=opcoes.paginas_por_taxon,
                semente=opcoes.semente,
            )
        )
    except (OSError, ValueError) as erro:
        parser.error(str(erro))
        return 2
    print(json.dumps(relatorio, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
