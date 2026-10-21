"""Valida filtros, proveniência e retomada da coleta pública."""

from __future__ import annotations

import io
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from PIL import Image

from training.coletar_inaturalist import (
    GRUPOS_TAXONS,
    ConfiguracaoColeta,
    coletar_fotos,
)


class ClienteFalso:
    """Responde à API com metadados mínimos e imagens locais."""

    def __init__(self) -> None:
        self.urls: list[str] = []
        self.downloads: list[str] = []
        self._taxons = {
            nome: indice + 1
            for indice, nome in enumerate(
                nome for taxons in GRUPOS_TAXONS.values() for nome in taxons
            )
        }

    def obter_json(self, url: str) -> object:
        self.urls.append(url)
        consulta = parse_qs(urlparse(url).query)
        if "/taxa/autocomplete" in url:
            nome = consulta["q"][0]
            return {"results": [{"id": self._taxons[nome], "name": nome}]}
        id_taxon = int(consulta["taxon_id"][0])
        return {
            "results": [
                {
                    "id": id_taxon + 10_000,
                    "user": {"login": f"autor-{id_taxon}"},
                    "photos": [
                        {
                            "id": id_taxon * 10,
                            "url": (
                                "https://inaturalist-open-data.s3.amazonaws.com/"
                                f"photos/{id_taxon}/square.jpg"
                            ),
                            "license_code": "cc-by-nc-nd",
                            "attribution": "Autor sem licença compatível",
                        },
                        {
                            "id": id_taxon * 10 + 1,
                            "url": (
                                "https://inaturalist-open-data.s3.amazonaws.com/"
                                f"photos/{id_taxon}/square.jpg"
                            ),
                            "license_code": "cc-by",
                            "attribution": f"Autoria pública {id_taxon}",
                        },
                    ],
                }
            ]
        }

    def baixar(self, url: str) -> bytes:
        self.downloads.append(url)
        buffer = io.BytesIO()
        Image.new("RGB", (12, 12), (40, 80, 120)).save(buffer, format="PNG")
        return buffer.getvalue()


def test_coleta_aplica_licenca_registra_autoria_e_reutiliza_cache(
    tmp_path: Path,
) -> None:
    """Seleciona uma foto por grupo e retoma sem repetir chamadas ou downloads."""
    cliente = ClienteFalso()
    configuracao = ConfiguracaoColeta(
        diretorio_dados=tmp_path,
        fotos_por_grupo=1,
        paginas_por_taxon=1,
        semente=12,
    )

    relatorio = coletar_fotos(configuracao, cliente)

    caminho_manifesto = tmp_path / "inaturalist" / "manifesto_coleta.json"
    manifesto = json.loads(caminho_manifesto.read_text(encoding="utf-8"))
    fotos = manifesto["fotos"]
    esperado_por_grupo = {grupo: len(taxons) for grupo, taxons in GRUPOS_TAXONS.items()}
    assert relatorio["fotos_baixadas"] == sum(esperado_por_grupo.values())
    assert relatorio["fotos_por_grupo"] == esperado_por_grupo
    assert all(
        {
            "id_observacao",
            "url",
            "autor",
            "licenca",
            "taxon",
            "grupo",
        }
        <= foto.keys()
        for foto in fotos
    )
    assert all(foto["licenca"] == "cc-by" for foto in fotos)
    assert all("/medium." in foto["url"] for foto in fotos)
    assert len(cliente.downloads) == sum(esperado_por_grupo.values())
    assert len(list((tmp_path / "inaturalist" / "fotos").rglob("*.png"))) == sum(
        esperado_por_grupo.values()
    )
    consulta_observacao = next(url for url in cliente.urls if "/observations?" in url)
    parametros = parse_qs(urlparse(consulta_observacao).query)
    assert parametros["place_id"] == ["6878"]
    assert parametros["quality_grade"] == ["research"]

    cliente_retomada = ClienteFalso()
    coletar_fotos(configuracao, cliente_retomada)
    assert cliente_retomada.urls == []
    assert cliente_retomada.downloads == []


def test_recusa_meta_de_fotos_nao_positiva(tmp_path: Path) -> None:
    """Rejeita uma meta inválida antes de consultar qualquer serviço."""
    try:
        ConfiguracaoColeta(diretorio_dados=tmp_path, fotos_por_grupo=0)
    except ValueError as erro:
        assert "positiva" in str(erro)
    else:
        raise AssertionError("Uma meta zero deveria ser recusada.")
