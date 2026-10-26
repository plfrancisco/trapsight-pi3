"""O inventário de manchas é fixo e não confunde ignoradas com insetos."""

import numpy as np

from training.completar_mascaras_bases import (
    completar,
    detectar_manchas,
    medir_completude,
)


def _cena():
    rgb = np.full((90, 100, 3), 230, dtype=np.uint8)
    classes = np.ones((90, 100), dtype=np.uint8)
    rgb[20:25, 20:25] = 60
    rgb[50:55, 60:65] = 80
    rgb[10:11, 10:90] = 0  # linha excluída pelo maior lado
    rgb[70:72, 20:22] = 20  # ruído menor que 12 pixels
    return rgb, classes


class Preditor:
    def set_image(self, rgb):
        self.rgb = rgb

    def reset_image(self):
        pass

    def segmentar_recorte(self, caixa, roi):
        x0, y0, x1, y1 = roi
        return (self.rgb[y0:y1, x0:x1, 0] < 100), 0.95 if caixa.x0 < 40 else 0.1


def test_protocolo_exclui_ruido_grade_e_conta_metade_do_componente():
    rgb, classes = _cena()
    assert len(detectar_manchas(rgb, classes)[1]) == 2
    classes[20:22, 20:25] = 2
    assert medir_completude(rgb, classes)["rotuladas"] == 0
    classes[22, 20:25] = 2
    assert medir_completude(rgb, classes)["rotuladas"] == 1


def test_sam_aceita_inseto_e_marca_proposta_ambigua_como_ignorada():
    rgb, original = _cena()
    nova, decisoes = completar(rgb, original, Preditor())
    assert medir_completude(rgb, original)["nao_resolvidas"] == 2
    depois = medir_completude(rgb, nova)
    assert depois == {
        "manchas": 2,
        "rotuladas": 1,
        "ignoradas": 1,
        "nao_resolvidas": 0,
        "completude": 1.0,
    }
    assert set(np.unique(original)) == {1}
    assert {d["decisao"] for d in decisoes} == {"sam_aceita", "ignorada_ambigua"}


def test_revisao_exclui_texto_mesmo_quando_sam_o_aceitaria():
    rgb, original = _cena()
    indice = detectar_manchas(rgb, original)[1][0][0]
    nova, _ = completar(rgb, original, Preditor(), {indice})
    assert medir_completude(rgb, nova)["ignoradas"] == 2
