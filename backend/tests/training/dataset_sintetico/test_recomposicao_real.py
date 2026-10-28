"""Verifica a separação por placa e a composição de recortes reais."""

from __future__ import annotations

import json
import random
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

import training.dataset_sintetico as modulo_dataset
from training.dataset_sintetico import (
    FAIXAS_ALVO_RECOMPOSICAO,
    NOMES_BASES_REAIS,
    BasePlacaReal,
    ConfiguracaoDataset,
    RecorteInsetoReal,
    _bases_compativeis_com_alvo,
    _carregar_recortes_coco,
    _compor_recortes_reais,
    _criar_base_sintetica,
    _criar_divisoes_por_faixa,
    _desenhar_distratores,
    _dividir_placas_reais,
    _extrair_recortes_reais,
    _particionar_fontes,
    classificar_faixa_cobertura_real,
    generate_dataset,
)
from training.medicoes_recomposicao import medir_espalhamento


def _criar_conjunto_real(diretorio: Path) -> tuple[Path, list[str]]:
    imagens = diretorio / "imagens"
    mascaras = diretorio / "mascaras"
    imagens.mkdir(parents=True)
    mascaras.mkdir(parents=True)
    nomes = [Path(nome).name for nome in NOMES_BASES_REAIS]
    nomes.extend(("placa_avaliacao_a.png", "placa_avaliacao_b.png"))
    for indice, nome in enumerate(nomes):
        imagem = Image.new("RGB", (320, 240), (236, 236, 232))
        desenho_imagem = ImageDraw.Draw(imagem)
        desenho_imagem.rectangle((30, 55, 289, 184), fill=(232, 230, 221))
        mascara = Image.new("L", (320, 240), 0)
        desenho_mascara = ImageDraw.Draw(mascara)
        desenho_mascara.rectangle((30, 55, 289, 184), fill=1)
        desenho_imagem.rectangle((52, 72, 59, 79), fill=(45, 38, 30))
        desenho_mascara.rectangle((52, 72, 59, 79), fill=2)
        desenho_imagem.rectangle((100, 90, 107, 97), fill=(31, 28, 24))
        desenho_mascara.rectangle((100, 90, 107, 97), fill=2)
        if indice == 0:
            desenho_mascara.rectangle((135, 110, 136, 111), fill=2)
            desenho_mascara.rectangle((160, 130, 190, 132), fill=2)
        imagem.save(imagens / nome)
        mascara.save(mascaras / nome)
    return diretorio, nomes


def _configurar_saida(
    fonte: Path,
    saida: Path,
    *,
    semente: int = 321,
    quantidade: int = 6,
    limite_colagens: int = 30,
) -> ConfiguracaoDataset:
    return ConfiguracaoDataset(
        diretorio_saida=saida,
        semente=semente,
        idade_maxima_dias=90,
        quantidade=quantidade,
        resolucao=(320, 240),
        limite_sprites=limite_colagens,
        diretorio_placas_reais=fonte,
        proporcao_bases_reais=0.5,
        intensidade_aglomeracao=0.75,
        limite_reuso_recorte=2,
        proporcao_placas_avaliacao=0.25,
    )


def test_divisao_separa_placas_e_forca_bases_reais_na_composicao(
    tmp_path: Path,
) -> None:
    fonte, nomes = _criar_conjunto_real(tmp_path / "fonte")

    composicao, avaliacao = _dividir_placas_reais(fonte, 19, 0.25)

    ids_composicao = {caminho.name for caminho in composicao}
    ids_avaliacao = {caminho.name for caminho in avaliacao}
    assert len(composicao) == 6
    assert len(avaliacao) == 2
    assert ids_composicao.isdisjoint(ids_avaliacao)
    assert set(Path(nome).name for nome in NOMES_BASES_REAIS) <= ids_composicao
    assert ids_composicao | ids_avaliacao == set(nomes)


@pytest.mark.parametrize(
    ("quantidades_faixas", "esperado"),
    [((10, 10, 10), (21, 5, 4)), ((1000, 1000, 1000), (2100, 450, 450))],
)
def test_divisao_estratificada_respeita_70_15_15_global_e_por_faixa(
    quantidades_faixas: tuple[int, int, int], esperado: tuple[int, int, int]
) -> None:
    faixas = [
        indice_faixa
        for indice_faixa, quantidade in enumerate(quantidades_faixas)
        for _ in range(quantidade)
    ]

    divisao = _criar_divisoes_por_faixa(faixas, semente=20261021)

    nomes = ("treino", "validacao", "teste")
    assert tuple(divisao.count(nome) for nome in nomes) == esperado
    for indice_faixa in range(3):
        tamanho = quantidades_faixas[indice_faixa]
        contagem = tuple(
            sum(
                divisao[indice] == nome
                for indice, faixa in enumerate(faixas)
                if faixa == indice_faixa
            )
            for nome in nomes
        )
        assert all(
            abs(contagem[indice] - tamanho * proporcao) <= 1
            for indice, proporcao in enumerate((0.70, 0.15, 0.15))
        )
    assert divisao == _criar_divisoes_por_faixa(faixas, semente=20261021)


@pytest.mark.parametrize(
    ("percentual", "esperada"),
    [
        (9.999, "ok"),
        (10.0, "atencao"),
        (20.0, "atencao"),
        (20.001, "trocar"),
    ],
)
def test_faixa_e_classificada_pela_cobertura_real(percentual, esperada):
    assert classificar_faixa_cobertura_real(percentual) == esperada


def test_alvos_compensam_um_ponto_perdido_pela_tolerancia():
    assert FAIXAS_ALVO_RECOMPOSICAO == (
        ("ok", 1.0, 10.9),
        ("atencao", 11.0, 20.9),
        ("trocar", 21.0, 55.0),
    )


def test_extracao_preserva_alfa_e_aplica_area_e_proporcao(
    tmp_path: Path,
) -> None:
    fonte, _ = _criar_conjunto_real(tmp_path / "fonte")
    composicao, _ = _dividir_placas_reais(fonte, 19, 0.25)
    bases = tuple(
        BasePlacaReal(
            identificador=caminho.stem,
            imagem=Image.open(caminho).convert("RGB"),
            mascara=Image.open(fonte / "mascaras" / caminho.name).convert("L"),
            percentual_herdado=1.0,
        )
        for caminho in composicao
    )

    recortes, componentes, aceitos = _extrair_recortes_reais(bases)

    primeiro = next(
        recorte
        for recorte in recortes
        if recorte.placa_origem == Path(NOMES_BASES_REAIS[0]).stem
    )
    alfa = np.asarray(primeiro.imagem.getchannel("A"))
    assert alfa.max() == 255
    assert np.count_nonzero(alfa) == 64
    assert componentes[Path(NOMES_BASES_REAIS[0]).stem] == 4
    assert aceitos[Path(NOMES_BASES_REAIS[0]).stem] == 2


def test_base_sintetica_k45_tem_proporcao_textura_e_sem_grade() -> None:
    imagem, mascara = _criar_base_sintetica((768, 576), random.Random(902))
    classes = np.asarray(mascara)
    ys, xs = np.nonzero(classes == 1)
    pixels = np.asarray(imagem)
    largura = int(xs.max() - xs.min() + 1)
    altura = int(ys.max() - ys.min() + 1)
    centro = pixels[int((ys.min() + ys.max()) / 2), int((xs.min() + xs.max()) / 2)]
    borda = pixels[int(ys.min() + 1), int((xs.min() + xs.max()) / 2)]

    assert abs(largura / altura - 450 / 220) < 0.02
    assert np.all(np.abs(centro.astype(int) - np.array((232, 230, 221))) <= 2)
    assert borda[0] > borda[2]
    assert set(np.unique(classes)) == {0, 1}


def test_recomposicao_uniforme_nao_encosta_recortes_para_formar_focos() -> None:
    imagem = Image.new("RGB", (320, 240), (236, 236, 232))
    mascara = Image.new("L", (320, 240), 0)
    ImageDraw.Draw(imagem).rectangle((30, 55, 289, 184), fill=(232, 230, 221))
    ImageDraw.Draw(mascara).rectangle((30, 55, 289, 184), fill=1)
    recortes = [
        RecorteInsetoReal(
            identificador=f"inseto_{indice}",
            placa_origem="origem",
            imagem=Image.new("RGBA", (5, 5), (20, 18, 16, 255)),
            area_px=25,
        )
        for indice in range(80)
    ]

    resultado, rotulos, _ = _compor_recortes_reais(
        imagem,
        mascara,
        recortes,
        percentual_alvo=4.0,
        rng=random.Random(20261021),
        limite_colagens=80,
        limite_reuso=1,
        intensidade_aglomeracao=0.0,
        usos_globais=[0] * len(recortes),
    )

    medida = medir_espalhamento(
        np.asarray(resultado), np.asarray(rotulos), sem_grade=False
    )
    assert 2.9 <= medida["fracao_escura"] * 100 <= 4.0
    assert medida["aglomeracao"] == 0.0


def test_faixas_baixas_evitem_base_real_com_foco_escuro_herdado() -> None:
    bases = [
        BasePlacaReal(
            identificador=identificador,
            imagem=Image.new("RGB", (100, 100)),
            mascara=Image.new("L", (100, 100)),
            percentual_herdado=0.0,
        )
        for identificador in ("base_lisa", "base_aglomerada")
    ]
    medidas = {"base_lisa": 0.0, "base_aglomerada": 0.16}

    assert _bases_compativeis_com_alvo(bases, 12.0, medidas) == [bases[0]]
    assert _bases_compativeis_com_alvo(bases, 24.0, medidas) == bases


def test_geracao_exclui_fontes_de_avaliacao_e_respeita_metadados(
    tmp_path: Path,
) -> None:
    fonte, _ = _criar_conjunto_real(tmp_path / "fonte")
    saida = tmp_path / "gerado"
    registros = generate_dataset(_configurar_saida(fonte, saida))
    relatorio = json.loads((saida / "relatorio_geracao.json").read_text("utf-8"))
    ids_avaliacao = set(relatorio["separacao_placas"]["avaliacao"])
    comparacao = relatorio["descritores_visuais"]

    assert len(registros) == 6
    assert relatorio["bases_reais_usadas"] == 3
    assert relatorio["bases_sinteticas_usadas"] == 3
    assert relatorio["extracao_recortes"]["recortes_aceitos"] == 12
    assert all(
        not ids_avaliacao.intersection(registro["placas_origem_recortes"])
        for registro in registros
    )
    donos = {}
    for registro in registros:
        fontes = set(registro["placas_origem_recortes"])
        if registro["placa_base_id"]:
            fontes.add(registro["placa_base_id"])
        for fonte in fontes:
            donos.setdefault(fonte, set()).add(registro["conjunto"])
    assert all(len(conjuntos) == 1 for conjuntos in donos.values())
    assert all(
        registro["maior_reuso_recorte_na_amostra"] <= 2 for registro in registros
    )
    assert comparacao["regiao"] == "pixels da superfície da placa (classes 1 e 2)"
    assert (
        comparacao["componentes_escuros_maior_lado_ks"][
            "componentes_referencia_69_placas"
        ]
        == 5144
    )
    assert all(
        abs(
            registro["percentual_cobertura_real"]
            - registro["cobertura_herdada_base_percentual"]
            - registro["cobertura_adicionada_percentual"]
        )
        < 1e-9
        for registro in registros
    )
    for registro in registros:
        caminho = saida / "mascaras" / f"{registro['id']}.png"
        with Image.open(caminho) as imagem:
            valores = set(np.unique(np.asarray(imagem)).tolist())
            percentual = (
                100
                * np.count_nonzero(np.asarray(imagem) == 2)
                / np.count_nonzero(np.asarray(imagem) > 0)
            )
        assert valores <= {0, 1, 2}
        assert abs(percentual - registro["percentual_cobertura_real"]) < 1e-9
        assert registro["faixa_cobertura_real"] == classificar_faixa_cobertura_real(
            registro["percentual_cobertura_real"]
        )


def test_recomposicao_real_e_deterministica(tmp_path: Path) -> None:
    fonte, _ = _criar_conjunto_real(tmp_path / "fonte")
    primeira = tmp_path / "primeira"
    segunda = tmp_path / "segunda"
    generate_dataset(_configurar_saida(fonte, primeira, quantidade=3))
    generate_dataset(_configurar_saida(fonte, segunda, quantidade=3))

    arquivos_primeiros = {
        caminho.relative_to(primeira): caminho.read_bytes()
        for caminho in primeira.rglob("*")
        if caminho.is_file()
    }
    arquivos_segundos = {
        caminho.relative_to(segunda): caminho.read_bytes()
        for caminho in segunda.rglob("*")
        if caminho.is_file()
    }
    assert arquivos_primeiros == arquivos_segundos


def test_recomposicao_real_retorna_do_checkpoint_sem_mudar_resultado(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fonte, _ = _criar_conjunto_real(tmp_path / "fonte")
    interrompida = tmp_path / "retomar"
    referencia = tmp_path / "referencia"
    configuracao = _configurar_saida(fonte, interrompida, quantidade=6)
    compor_original = modulo_dataset._compor_recortes_reais
    chamadas = 0

    def interromper_segunda_amostra(*args, **kwargs):
        nonlocal chamadas
        chamadas += 1
        if chamadas == 2:
            raise RuntimeError("interrupção simulada")
        return compor_original(*args, **kwargs)

    monkeypatch.setattr(
        modulo_dataset, "_compor_recortes_reais", interromper_segunda_amostra
    )
    with pytest.raises(RuntimeError, match="interrupção simulada"):
        generate_dataset(configuracao)
    assert (
        json.loads((interrompida / ".progresso.json").read_text())[
            "amostras_concluidas"
        ]
        == 1
    )

    monkeypatch.setattr(modulo_dataset, "_compor_recortes_reais", compor_original)
    retomadas = generate_dataset(configuracao)
    completas = generate_dataset(_configurar_saida(fonte, referencia, quantidade=6))

    arquivos_retomados = {
        caminho.relative_to(interrompida): caminho.read_bytes()
        for caminho in interrompida.rglob("*")
        if caminho.is_file()
    }
    arquivos_completos = {
        caminho.relative_to(referencia): caminho.read_bytes()
        for caminho in referencia.rglob("*")
        if caminho.is_file()
    }
    assert arquivos_retomados == arquivos_completos
    assert retomadas == completas


def test_recomposicao_para_no_checkpoint_e_retomavel(tmp_path: Path) -> None:
    fonte, _ = _criar_conjunto_real(tmp_path / "fonte")
    interrompida = tmp_path / "parcial"
    referencia = tmp_path / "referencia"
    configuracao = _configurar_saida(fonte, interrompida, quantidade=6)

    parcial = generate_dataset(configuracao, parar_apos=2)

    assert len(parcial) == 2
    assert (
        json.loads((interrompida / ".progresso.json").read_text())[
            "amostras_concluidas"
        ]
        == 2
    )
    assert not (interrompida / "relatorio_geracao.json").exists()

    completa = generate_dataset(configuracao)
    esperada = generate_dataset(_configurar_saida(fonte, referencia, quantidade=6))

    assert completa == esperada
    assert (interrompida / "relatorio_geracao.json").is_file()


def test_seis_bases_particionadas_em_quatro_um_um_antes_da_composicao(tmp_path):
    fonte, _ = _criar_conjunto_real(tmp_path / "fonte")
    composicao, _ = _dividir_placas_reais(fonte, 19, 0.25)
    grupos = _particionar_fontes(composicao, 19)
    assert [len(g) for g in grupos.values()] == [4, 1, 1]
    assert set().union(*map(set, grupos.values())) == set(composicao)
    assert sum(map(len, grupos.values())) == len(composicao)


def test_particao_reduzida_distribui_quatro_bases_elegiveis_sem_cruzamento(tmp_path):
    fonte, _ = _criar_conjunto_real(tmp_path / "fonte")
    composicao, _ = _dividir_placas_reais(fonte, 19, 0.25)
    elegiveis = {Path(nome).stem for nome in NOMES_BASES_REAIS[:4]}

    grupos = _particionar_fontes(composicao, 19, elegiveis)

    assert [sum(p.stem in elegiveis for p in grupos[n]) for n in grupos] == [2, 1, 1]
    assert set().union(*map(set, grupos.values())) == set(composicao)
    assert all(
        set(grupos[a]).isdisjoint(grupos[b])
        for a, b in (
            ("treino", "validacao"),
            ("treino", "teste"),
            ("validacao", "teste"),
        )
    )


def test_biblioteca_coco_carrega_so_recortes_aprovados_e_preserva_proveniencia(
    tmp_path: Path,
):
    biblioteca = tmp_path / "recortes"
    (biblioteca / "catalogos").mkdir(parents=True)
    (biblioteca / "placa_a").mkdir()
    imagem = Image.new("RGBA", (10, 8), (42, 30, 20, 0))
    ImageDraw.Draw(imagem).rectangle((2, 2, 4, 5), fill=(42, 30, 20, 255))
    imagem.save(biblioteca / "placa_a" / "00000001.png")
    (biblioteca / "catalogos" / "placa_a.jsonl").write_text(
        "\n".join(
            (
                json.dumps(
                    {
                        "placa_origem": "placa_a",
                        "anotacao_coco_id": 1,
                        "taxon": "Diptera",
                        "aprovada": True,
                        "arquivo": "placa_a/00000001.png",
                        "area_projetada_px": 12,
                    }
                ),
                json.dumps(
                    {
                        "placa_origem": "placa_a",
                        "anotacao_coco_id": 2,
                        "taxon": "Coleoptera",
                        "aprovada": False,
                        "arquivo": None,
                        "area_projetada_px": 0,
                    }
                ),
            )
        )
        + "\n",
        encoding="utf-8",
    )

    recortes, encontrados, aceitos = _carregar_recortes_coco(biblioteca, {"placa_a"})

    assert encontrados == {"placa_a": 2}
    assert aceitos == {"placa_a": 1}
    assert len(recortes) == 1
    assert recortes[0].identificador == "placa_a__coco1"
    assert recortes[0].taxon == "Diptera"
    assert recortes[0].area_px == 12


def test_distratores_modificam_a_imagem_e_permanecem_em_placa_limpa():
    imagem, mascara = _criar_base_sintetica((320, 240), random.Random(1))
    antes = np.array(imagem)
    classes = np.array(mascara)
    ys, xs = np.nonzero(classes == 1)
    rgba = imagem.convert("RGBA")
    _desenhar_distratores(
        rgba,
        (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1),
        ["poeira", "pelos", "teia", "respingos"],
        random.Random(9),
    )
    alterados = np.any(np.array(rgba.convert("RGB")) != antes, axis=2)
    assert alterados.any()
    assert np.all(classes[alterados] == 1)
    assert np.array_equal(classes, np.array(mascara))


def test_expansao_atinge_cobertura_e_preserva_regioes_ignoradas(tmp_path):
    fonte, _ = _criar_conjunto_real(tmp_path / "fonte")
    base = BasePlacaReal(
        "placa",
        Image.open(fonte / "imagens" / NOMES_BASES_REAIS[1]).convert("RGB"),
        Image.open(fonte / "mascaras" / NOMES_BASES_REAIS[1]).convert("L"),
        1.0,
    )
    recortes, _, _ = _extrair_recortes_reais((base,))
    classes = np.array(base.mascara)
    classes[90:100, 180:190] = 255
    _, resultado, meta = _compor_recortes_reais(
        base.imagem,
        Image.fromarray(classes),
        recortes,
        25.0,
        random.Random(7),
        1000,
        500,
        0.7,
        [0] * len(recortes),
    )
    assert abs(meta["percentual_cobertura_real"] - 25.0) <= 1.0
    assert np.all(np.array(resultado)[classes == 255] == 255)
    assert meta["n_recortes"] <= 1000
