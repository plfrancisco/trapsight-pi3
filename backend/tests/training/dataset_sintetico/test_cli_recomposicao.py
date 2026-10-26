"""Os tetos do modo real não alteram a configuração legada."""

import pytest

from training import gerar_dataset


@pytest.mark.parametrize(
    "origem,limite,reuso", [("--placas-reais", 12000, 12), ("--sprites", 3000, 2)]
)
def test_cli_escolhe_tetos_por_modalidade(tmp_path, monkeypatch, origem, limite, reuso):
    capturadas = []
    monkeypatch.setattr(gerar_dataset, "diretorio_dados_configurado", lambda: tmp_path)
    monkeypatch.setattr(gerar_dataset, "load_sprite_catalog", lambda _: ())

    def gerar(configuracao, sprites):
        capturadas.append(configuracao)
        return [{"alvo_atingido": True}]

    monkeypatch.setattr(gerar_dataset, "generate_dataset", gerar)
    assert (
        gerar_dataset.main(
            [
                origem,
                str(tmp_path / "fonte"),
                "--saida",
                str(tmp_path / "saida"),
                "--semente",
                "17",
                "--idade-maxima-dias",
                "90",
            ]
        )
        == 0
    )
    assert capturadas[0].limite_sprites == limite
    assert capturadas[0].limite_reuso_recorte == reuso
