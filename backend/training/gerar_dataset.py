"""Interface de linha de comando para gerar o dataset sintético local."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from training.coletar_inaturalist import diretorio_dados_configurado
from training.dataset_sintetico import (
    K_ESCALA_MAXIMO,
    K_ESCALA_MINIMO,
    LIMITE_SPRITES_POR_AMOSTRA,
    PX_POR_MM_PADRAO,
    RESOLUCAO_PADRAO,
    ConfiguracaoDataset,
    generate_dataset,
    load_sprite_catalog,
)


def criar_parser() -> argparse.ArgumentParser:
    """Cria o parser dos parâmetros do gerador.

    Returns:
        Parser configurado com diretórios, volume e parâmetros reprodutíveis.
    """
    parser = argparse.ArgumentParser(
        description="Gera imagens sintéticas, máscaras e metadados do TrapSight."
    )
    parser.add_argument(
        "--sprites",
        type=Path,
        required=True,
        help="Diretório do banco local com manifest.json e sprites PNG.",
    )
    parser.add_argument(
        "--saida",
        type=Path,
        required=True,
        help="Diretório novo ou vazio fora do código-fonte versionado.",
    )
    parser.add_argument(
        "--semente",
        type=int,
        required=True,
        help="Semente global para reproduzir exatamente a geração.",
    )
    parser.add_argument(
        "--idade-maxima-dias",
        type=float,
        required=True,
        help="Idade máxima calibrada do refil, em dias.",
    )
    parser.add_argument(
        "--quantidade",
        type=int,
        default=3000,
        help="Quantidade de imagens (padrão: 3000).",
    )
    parser.add_argument(
        "--largura",
        type=int,
        default=RESOLUCAO_PADRAO[0],
        help=f"Largura de saída em pixels (padrão: {RESOLUCAO_PADRAO[0]}).",
    )
    parser.add_argument(
        "--altura",
        type=int,
        default=RESOLUCAO_PADRAO[1],
        help=f"Altura de saída em pixels (padrão: {RESOLUCAO_PADRAO[1]}).",
    )
    parser.add_argument(
        "--limite-sprites",
        type=int,
        default=LIMITE_SPRITES_POR_AMOSTRA,
        help=(
            "Máximo de tentativas de composição por imagem "
            f"(padrão: {LIMITE_SPRITES_POR_AMOSTRA})."
        ),
    )
    parser.add_argument(
        "--px-por-mm",
        type=float,
        default=PX_POR_MM_PADRAO,
        help=f"Escala de referência da placa (padrão: {PX_POR_MM_PADRAO}).",
    )
    parser.add_argument(
        "--k-escala-min",
        type=float,
        default=K_ESCALA_MINIMO,
        help=f"Menor k visual (padrão: {K_ESCALA_MINIMO}).",
    )
    parser.add_argument(
        "--k-escala-max",
        type=float,
        default=K_ESCALA_MAXIMO,
        help=f"Maior k visual (padrão: {K_ESCALA_MAXIMO}).",
    )
    parser.add_argument(
        "--pesos-grupo",
        type=_ler_pesos_grupo,
        help=(
            "Pesos JSON por grupo; por padrão, 70%% voadores e 30%% rasteiros "
            "(distribuídos igualmente dentro de cada conjunto)."
        ),
    )
    return parser


def _ler_pesos_grupo(valor: str) -> dict[str, float]:
    try:
        dados = json.loads(valor)
    except json.JSONDecodeError as erro:
        raise argparse.ArgumentTypeError(
            "Os pesos precisam ser um objeto JSON."
        ) from erro
    if not isinstance(dados, dict) or any(
        not isinstance(peso, (int, float)) or isinstance(peso, bool)
        for peso in dados.values()
    ):
        raise argparse.ArgumentTypeError("Os pesos precisam mapear grupos a números.")
    return {str(grupo): float(peso) for grupo, peso in dados.items()}


def main(argumentos: list[str] | None = None) -> int:
    """Valida os parâmetros e executa o gerador.

    Args:
        argumentos: Argumentos da linha de comando; usa `sys.argv` se ausente.

    Returns:
        Código de saída zero em caso de sucesso ou dois para entradas inválidas.
    """
    parser = criar_parser()
    opcoes = parser.parse_args(argumentos)
    try:
        dados_externos = diretorio_dados_configurado()
        if not opcoes.sprites.resolve().is_relative_to(dados_externos):
            raise ValueError("O banco precisa ficar em TRAPSIGHT_TRAINING_DATA_DIR.")
        if not opcoes.saida.resolve().is_relative_to(dados_externos):
            raise ValueError("A saída precisa ficar em TRAPSIGHT_TRAINING_DATA_DIR.")
        sprites = load_sprite_catalog(opcoes.sprites)
        configuracao = ConfiguracaoDataset(
            diretorio_saida=opcoes.saida,
            semente=opcoes.semente,
            idade_maxima_dias=opcoes.idade_maxima_dias,
            quantidade=opcoes.quantidade,
            resolucao=(opcoes.largura, opcoes.altura),
            limite_sprites=opcoes.limite_sprites,
            pesos_grupo=opcoes.pesos_grupo,
            px_por_mm=opcoes.px_por_mm,
            k_escala_min=opcoes.k_escala_min,
            k_escala_max=opcoes.k_escala_max,
        )
        inicio = time.perf_counter()
        registros = generate_dataset(configuracao, sprites)
    except (OSError, ValueError) as erro:
        parser.error(str(erro))
        return 2

    print(f"Dataset gerado: {opcoes.saida.resolve()}")
    print(f"Amostras: {len(registros)}")
    print(f"Sprites catalogados: {len(sprites)}")
    print(f"Semente global: {opcoes.semente}")
    print(
        "Alvos atingidos: "
        f"{sum(registro['alvo_atingido'] is True for registro in registros)}"
    )
    print(f"Tempo por imagem: {(time.perf_counter() - inicio) / len(registros):.3f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
