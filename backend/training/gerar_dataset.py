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
    origem = parser.add_mutually_exclusive_group(required=True)
    origem.add_argument(
        "--sprites",
        type=Path,
        help="Catálogo legado com manifest.json e sprites PNG.",
    )
    origem.add_argument(
        "--placas-reais",
        type=Path,
        help="Diretório com imagens/, mascaras/ e placas UMS reais.",
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
        "--parar-apos",
        type=int,
        help=(
            "Interrompe após N amostras e mantém o checkpoint para retomada; "
            "uso de validação de reprodutibilidade."
        ),
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
        default=None,
        help=(
            "Máximo de tentativas de composição por imagem "
            "(padrão: 12000 na recomposição real; 3000 no modo legado)."
        ),
    )
    parser.add_argument(
        "--proporcao-bases-reais",
        type=float,
        default=0.5,
        help="Fração de bases reais na recomposição (padrão: 0.5).",
    )
    parser.add_argument(
        "--mascaras-bases",
        type=Path,
        help="Diretório de máscaras v5, com configuracao.json no pai.",
    )
    parser.add_argument(
        "--recortes-reais",
        type=Path,
        help="Biblioteca COCO/SAM de recortes com catálogo de proveniência.",
    )
    parser.add_argument(
        "--intensidade-aglomeracao",
        type=float,
        default=0.0,
        help="Fração da área nova concentrada em grupos (padrão: 0.0, uniforme).",
    )
    parser.add_argument(
        "--fator-escala-recorte",
        type=float,
        default=1.0,
        help="Fator de escala para calibrar colagens reais (padrão: 1.0).",
    )
    parser.add_argument(
        "--limite-reuso-recorte",
        type=int,
        default=None,
        help="Máximo de vezes por recorte e amostra (padrão: 2).",
    )
    parser.add_argument(
        "--proporcao-placas-avaliacao",
        type=float,
        default=0.2,
        help="Fração de placas isolada para avaliação (padrão: 0.2).",
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
        raiz_repo = Path(__file__).resolve().parents[2]

        def dentro_dos_dados(caminho: Path | None) -> bool:
            if caminho is None:
                return True
            caminho_resolvido = caminho.resolve()
            return caminho_resolvido.is_relative_to(dados_externos) or (
                caminho_resolvido.is_relative_to(raiz_repo / "dataset")
            )

        if not dentro_dos_dados(opcoes.saida):
            raise ValueError(
                "A saída precisa ficar em TRAPSIGHT_TRAINING_DATA_DIR ou dataset/."
            )
        if opcoes.sprites is not None:
            if opcoes.parar_apos is not None:
                raise ValueError("--parar-apos só é válido com --placas-reais.")
            if not dentro_dos_dados(opcoes.sprites):
                raise ValueError(
                    "O banco de sprites precisa ficar em TRAPSIGHT_TRAINING_DATA_DIR."
                )
            sprites = load_sprite_catalog(opcoes.sprites)
        else:
            if not dentro_dos_dados(opcoes.placas_reais):
                raise ValueError(
                    "As placas reais precisam ficar nos dados de treino ou em dataset/."
                )
            sprites = ()
        if not dentro_dos_dados(opcoes.mascaras_bases) or not dentro_dos_dados(
            opcoes.recortes_reais
        ):
            raise ValueError(
                "Máscaras e recortes precisam ficar nos dados de treino ou em dataset/."
            )
        if opcoes.mascaras_bases is not None and opcoes.recortes_reais is None:
            raise ValueError(
                "Máscaras v5 exigem a biblioteca de recortes COCO/SAM correspondente."
            )
        configuracao = ConfiguracaoDataset(
            diretorio_saida=opcoes.saida,
            semente=opcoes.semente,
            idade_maxima_dias=opcoes.idade_maxima_dias,
            quantidade=opcoes.quantidade,
            resolucao=(opcoes.largura, opcoes.altura),
            limite_sprites=opcoes.limite_sprites
            if opcoes.limite_sprites is not None
            else (12000 if opcoes.placas_reais else LIMITE_SPRITES_POR_AMOSTRA),
            pesos_grupo=opcoes.pesos_grupo,
            px_por_mm=opcoes.px_por_mm,
            k_escala_min=opcoes.k_escala_min,
            k_escala_max=opcoes.k_escala_max,
            diretorio_placas_reais=opcoes.placas_reais,
            diretorio_mascaras_bases=opcoes.mascaras_bases,
            diretorio_recortes_reais=opcoes.recortes_reais,
            proporcao_bases_reais=opcoes.proporcao_bases_reais,
            intensidade_aglomeracao=opcoes.intensidade_aglomeracao,
            fator_escala_recorte=opcoes.fator_escala_recorte,
            limite_reuso_recorte=opcoes.limite_reuso_recorte
            if opcoes.limite_reuso_recorte is not None
            else 2,
            proporcao_placas_avaliacao=opcoes.proporcao_placas_avaliacao,
        )
        inicio = time.perf_counter()
        if opcoes.parar_apos is None:
            registros = generate_dataset(configuracao, sprites)
        else:
            registros = generate_dataset(
                configuracao, sprites, parar_apos=opcoes.parar_apos
            )
    except (OSError, ValueError) as erro:
        parser.error(str(erro))
        return 2

    print(f"Dataset gerado: {opcoes.saida.resolve()}")
    print(f"Amostras: {len(registros)}")
    if opcoes.sprites is not None:
        print(f"Sprites catalogados: {len(sprites)}")
    else:
        print(f"Placas reais: {opcoes.placas_reais.resolve()}")
    print(f"Semente global: {opcoes.semente}")
    if opcoes.parar_apos is not None:
        print(f"Checkpoint retomável: {opcoes.saida.resolve() / '.progresso.json'}")
        return 0
    print(
        "Alvos atingidos: "
        f"{sum(registro['alvo_atingido'] is True for registro in registros)}"
    )
    print(f"Tempo por imagem: {(time.perf_counter() - inicio) / len(registros):.3f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
