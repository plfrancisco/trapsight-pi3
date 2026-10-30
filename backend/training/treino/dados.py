"""Leitura, verificação e carregamento do dataset sintético.

O treino recusa começar quando o dataset viola a divisão por semente ou quando
o gabarito não confere com os metadados (treino_spec.md, seção 6.1). A
conferência pixel a pixel nunca lê imagens do conjunto de teste: ele só é
aberto na avaliação final (seção 6.2).
"""

from __future__ import annotations

import hashlib
import json
import random
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image
from torch.utils.data import Dataset

from training.treino.configuracao import (
    INDICE_PLACA_COBERTA,
    INDICE_PLACA_LIMPA,
    derivar_status,
)

CONJUNTOS = ("treino", "validacao", "teste")
FAIXAS = ("ok", "atencao", "trocar")
PROPORCAO_FAIXA_MINIMA = 0.25
PROPORCAO_FAIXA_MAXIMA = 0.42
CORRELACAO_IDADE_MAXIMA = 0.1
TOLERANCIA_PERCENTUAL_PP = 0.01


class DatasetInvalido(ValueError):
    """O dataset viola uma regra que impede o treino de começar."""


@dataclass(frozen=True)
class Amostra:
    """Uma imagem sintética, o gabarito e os metadados usados nas análises."""

    identificador: str
    semente: int
    conjunto: str
    faixa: str
    percentual_real: float
    idade_dias: float
    dominante_cor: str
    imagem: Path
    mascara: Path
    placa_base_id: str | None = None
    placas_origem_recortes: tuple[str, ...] = ()
    origem_base: str | None = None
    subconjuntos_avaliacao: tuple[str, ...] = ()


@dataclass(frozen=True)
class InfoDataset:
    """Dataset lido: amostras, semente global e hash dos metadados."""

    raiz: Path
    amostras: tuple[Amostra, ...]
    semente_global: int
    hash_metadados: str

    def do_conjunto(self, conjunto: str) -> list[Amostra]:
        """Amostras de um conjunto, em ordem estável por identificador."""
        return sorted(
            (a for a in self.amostras if a.conjunto == conjunto),
            key=lambda a: a.identificador,
        )

    def sementes_por_conjunto(self) -> dict[str, list[int]]:
        """Sementes de geração de cada conjunto, para o registro da execução."""
        return {
            conjunto: sorted(a.semente for a in self.amostras if a.conjunto == conjunto)
            for conjunto in CONJUNTOS
        }


def hash_arquivo(caminho: Path) -> str:
    """SHA-256 de um arquivo, lido em blocos."""
    resumo = hashlib.sha256()
    with Path(caminho).open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            resumo.update(bloco)
    return resumo.hexdigest()


def percentual_da_mascara(mascara: np.ndarray) -> float | None:
    """Percentual coberto de uma máscara de rótulos (modelo_spec.md, seção 5).

    Devolve None quando não há pixel de placa, caso em que não há percentual.
    """
    contagens = np.bincount(mascara.ravel(), minlength=3)
    area_placa = int(contagens[INDICE_PLACA_LIMPA] + contagens[INDICE_PLACA_COBERTA])
    if area_placa == 0:
        return None
    return float(contagens[INDICE_PLACA_COBERTA]) / area_placa * 100.0


def ler_dataset(diretorio: Path) -> InfoDataset:
    """Lê `metadados.jsonl` e `configuracao.json` de um dataset gerado."""
    raiz = Path(diretorio).resolve()
    try:
        configuracao = json.loads((raiz / "configuracao.json").read_text("utf-8"))
        caminho_metadados = raiz / "metadados.jsonl"
        linhas = caminho_metadados.read_text("utf-8").splitlines()
    except FileNotFoundError as erro:
        raise DatasetInvalido(
            f"Arquivo obrigatório ausente: {erro.filename}."
        ) from erro
    except json.JSONDecodeError as erro:
        raise DatasetInvalido("configuracao.json precisa conter JSON válido.") from erro
    semente_global = configuracao.get("semente_global")
    if isinstance(semente_global, bool) or not isinstance(semente_global, int):
        raise DatasetInvalido("configuracao.json precisa registrar semente_global.")

    amostras: list[Amostra] = []
    for numero, linha in enumerate(linhas, start=1):
        if not linha.strip():
            continue
        try:
            dados: dict[str, Any] = json.loads(linha)
            identificador = str(dados["id"])
            if Path(identificador).name != identificador:
                raise ValueError("identificador com caminho")
            base = dados.get("placa_base_id")
            origens = dados.get("placas_origem_recortes", [])
            origem_base = dados.get("origem_base")
            subconjuntos = dados.get("subconjuntos_avaliacao", [])
            if origem_base is not None and (
                not isinstance(origem_base, str) or not origem_base.strip()
            ):
                raise ValueError("origem_base inválida")
            if not isinstance(subconjuntos, list) or any(
                s not in ("iluminacao_angulo", "sujeira", "amarelamento")
                for s in subconjuntos
            ):
                raise ValueError("subconjuntos_avaliacao inválidos")
            if base is not None and (not isinstance(base, str) or not base.strip()):
                raise ValueError("placa_base_id inválida")
            if not isinstance(origens, list) or any(
                not isinstance(origem, str) or not origem.strip() for origem in origens
            ):
                raise ValueError("placas_origem_recortes inválidas")
            percentual_real = float(dados["percentual_cobertura_real"])
            faixa_real = derivar_status(percentual_real)
            if (
                "faixa_cobertura_real" in dados
                and dados["faixa_cobertura_real"] != faixa_real
            ):
                raise ValueError("faixa_cobertura_real diverge da cobertura")
            faixa = str(
                dados.get("faixa_cobertura_real", dados["faixa_cobertura_alvo"])
            )
            amostras.append(
                Amostra(
                    identificador=identificador,
                    semente=int(dados["semente"]),
                    conjunto=str(dados["conjunto"]),
                    faixa=faixa,
                    percentual_real=percentual_real,
                    idade_dias=float(dados["idade_simulada_dias"]),
                    dominante_cor=str(dados.get("dominante_cor", "")),
                    imagem=raiz / "imagens" / f"{identificador}.png",
                    mascara=raiz / "mascaras" / f"{identificador}.png",
                    placa_base_id=base,
                    placas_origem_recortes=tuple(origens),
                    origem_base=origem_base,
                    subconjuntos_avaliacao=tuple(subconjuntos),
                )
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as erro:
            raise DatasetInvalido(f"Linha {numero} dos metadados inválida.") from erro
    if not amostras:
        raise DatasetInvalido("metadados.jsonl não contém amostras.")
    return InfoDataset(
        raiz=raiz,
        amostras=tuple(amostras),
        semente_global=semente_global,
        hash_metadados=hash_arquivo(caminho_metadados),
    )


def correlacao_idade_cobertura(amostras: Sequence[Amostra]) -> float:
    """Correlação de Pearson entre a idade simulada e a cobertura real."""
    if len(amostras) < 3:
        return 0.0
    idades = np.array([a.idade_dias for a in amostras], dtype=np.float64)
    coberturas = np.array([a.percentual_real for a in amostras], dtype=np.float64)
    if idades.std() == 0 or coberturas.std() == 0:
        return 0.0
    return float(np.corrcoef(idades, coberturas)[0, 1])


def verificar_estrutura(info: InfoDataset) -> list[str]:
    """Verificações feitas só com os metadados, em todos os conjuntos.

    Devolve a lista de problemas encontrados (vazia quando o dataset passa).
    """
    problemas: list[str] = []
    conjuntos_invalidos = {a.conjunto for a in info.amostras} - set(CONJUNTOS)
    if conjuntos_invalidos:
        problemas.append(f"Conjuntos desconhecidos: {sorted(conjuntos_invalidos)}.")

    identificadores = Counter(a.identificador for a in info.amostras)
    repetidos = [i for i, n in identificadores.items() if n > 1]
    if repetidos:
        problemas.append(f"Identificadores repetidos: {repetidos[:3]}.")

    conjunto_da_semente: dict[int, set[str]] = {}
    for amostra in info.amostras:
        conjunto_da_semente.setdefault(amostra.semente, set()).add(amostra.conjunto)
    compartilhadas = [s for s, c in conjunto_da_semente.items() if len(c) > 1]
    if compartilhadas:
        problemas.append(
            f"{len(compartilhadas)} semente(s) aparecem em mais de um conjunto."
        )

    conjuntos_por_placa: dict[str, set[str]] = {}
    for amostra in info.amostras:
        fontes = set(amostra.placas_origem_recortes)
        if amostra.placa_base_id is not None:
            fontes.add(amostra.placa_base_id)
        for placa in fontes:
            conjuntos_por_placa.setdefault(placa, set()).add(amostra.conjunto)
    for placa, conjuntos in sorted(conjuntos_por_placa.items()):
        if len(conjuntos) > 1:
            problemas.append(
                f"Placa de origem {placa} aparece em mais de um conjunto: "
                f"{', '.join(sorted(conjuntos))}."
            )

    for conjunto in CONJUNTOS:
        do_conjunto = info.do_conjunto(conjunto)
        if not do_conjunto:
            problemas.append(f"O conjunto {conjunto} está vazio.")
            continue
        contagem = Counter(a.faixa for a in do_conjunto)
        if len(do_conjunto) < 3:
            problemas.append(
                f"Conjunto {conjunto} tem menos de três amostras para cobrir as faixas."
            )
        elif len(do_conjunto) < 12:
            quantidades = [contagem.get(faixa, 0) for faixa in FAIXAS]
            if max(quantidades) - min(quantidades) > 1:
                problemas.append(
                    f"Faixas desbalanceadas em {conjunto}: {dict(contagem)}."
                )
        else:
            for faixa in FAIXAS:
                proporcao = contagem.get(faixa, 0) / len(do_conjunto)
                if not PROPORCAO_FAIXA_MINIMA <= proporcao <= PROPORCAO_FAIXA_MAXIMA:
                    problemas.append(
                        f"Faixa {faixa} em {conjunto} com {proporcao:.0%} das amostras."
                    )

    correlacao = correlacao_idade_cobertura(info.do_conjunto("treino"))
    if abs(correlacao) >= CORRELACAO_IDADE_MAXIMA:
        problemas.append(
            f"Correlação idade x cobertura no treino de {correlacao:.3f} (limite 0,1)."
        )
    return problemas


def verificar_mascaras(amostras: Sequence[Amostra]) -> list[str]:
    """Confere o percentual de cada máscara com o registrado nos metadados."""
    problemas: list[str] = []
    for amostra in amostras:
        try:
            with Image.open(amostra.mascara) as aberta:
                mascara = np.asarray(aberta.convert("L"), dtype=np.uint8)
        except (OSError, FileNotFoundError):
            problemas.append(f"Máscara ilegível: {amostra.identificador}.")
            continue
        if not np.isin(mascara, (0, 1, 2, 255)).all():
            problemas.append(f"Máscara com classe inválida: {amostra.identificador}.")
            continue
        percentual = percentual_da_mascara(mascara)
        if (
            percentual is None
            or abs(percentual - amostra.percentual_real) > TOLERANCIA_PERCENTUAL_PP
        ):
            problemas.append(
                f"Percentual da máscara diverge dos metadados: {amostra.identificador}."
            )
        if len(problemas) >= 10:
            break
    return problemas


def exigir_dataset_valido(info: InfoDataset) -> None:
    """Executa as verificações do treino e levanta `DatasetInvalido` se falharem.

    A conferência das máscaras cobre treino e validação; o teste só é aberto na
    avaliação final.
    """
    problemas = verificar_estrutura(info)
    problemas += verificar_mascaras(info.do_conjunto("treino"))
    problemas += verificar_mascaras(info.do_conjunto("validacao"))
    if problemas:
        raise DatasetInvalido(" ".join(problemas[:10]))


def amostrar(
    amostras: Sequence[Amostra], limite: int | None, semente: int
) -> list[Amostra]:
    """Subconjunto reprodutível, usado nos testes de fumaça."""
    amostras = list(amostras)
    if limite is None or limite >= len(amostras):
        return amostras
    sorteadas = random.Random(semente).sample(amostras, limite)
    return sorted(sorteadas, key=lambda a: a.identificador)


def contar_pixels_por_classe(amostras: Sequence[Amostra]) -> np.ndarray:
    """Contagem de pixels de cada classe sobre as máscaras do treino."""
    total = np.zeros(3, dtype=np.int64)
    for amostra in amostras:
        with Image.open(amostra.mascara) as aberta:
            total += np.bincount(
                np.asarray(aberta.convert("L"), dtype=np.uint8).ravel(), minlength=3
            )[:3]
    return total


def pesos_de_classe(contagens: np.ndarray, expoente: float, teto: float) -> np.ndarray:
    """Pesos por classe relativos à classe mais frequente, que recebe peso 1.

    `w_c = (f_máx / f_c)^expoente`, limitado a `teto` (treino_spec.md, seção
    3.3). O expoente 0,5 suaviza o peso de classes raras; o teto impede que uma
    classe quase ausente domine a perda. Só as razões importam: a entropia
    cruzada e o Dice dividem pela soma dos pesos.
    """
    frequencias = contagens.astype(np.float64) / max(int(contagens.sum()), 1)
    if np.any(frequencias <= 0):
        raise DatasetInvalido("Alguma classe não tem nenhum pixel no treino.")
    pesos = np.power(frequencias.max() / frequencias, expoente)
    return np.minimum(pesos, teto)


def derivar_semente(semente_global: int, epoca: int, indice: int) -> int:
    """Semente por amostra e época, independente da ordem dos workers."""
    return int(
        np.random.SeedSequence([semente_global, epoca, indice]).generate_state(1)[0]
    )


class DatasetSegmentacao(Dataset):
    """Pares imagem/máscara com augmentation reprodutível por amostra e época."""

    def __init__(
        self,
        amostras: Sequence[Amostra],
        transformacao: Callable[..., dict[str, Any]],
        semente_global: int,
        reprodutivel: bool = False,
    ) -> None:
        self.amostras = list(amostras)
        self.transformacao = transformacao
        self.semente_global = semente_global
        self.reprodutivel = reprodutivel
        self.epoca = 0

    def __len__(self) -> int:
        return len(self.amostras)

    def __getitem__(self, indice: int):
        amostra = self.amostras[indice]
        with Image.open(amostra.imagem) as aberta:
            imagem = np.asarray(aberta.convert("RGB"), dtype=np.uint8)
        with Image.open(amostra.mascara) as aberta:
            mascara = np.asarray(aberta.convert("L"), dtype=np.uint8)
        if imagem.shape[:2] != mascara.shape:
            raise DatasetInvalido(f"Dimensões divergentes: {amostra.identificador}.")
        if self.reprodutivel:
            self.transformacao.set_random_seed(
                derivar_semente(self.semente_global, self.epoca, indice)
            )
        resultado = self.transformacao(image=imagem, mask=mascara)
        return resultado["image"], resultado["mask"].long(), indice
