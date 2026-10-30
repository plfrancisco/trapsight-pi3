"""Linha de comando: `python -m training.treino <comando>`."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from training.treino.configuracao import CONFIGURACAO_PADRAO, carregar_configuracao


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m training.treino", description="Treino da U-Net de segmentação."
    )
    comandos = parser.add_subparsers(dest="comando", required=True)

    comandos.add_parser("gpu", help="mostra a GPU e a memória de vídeo disponíveis")

    treinar = comandos.add_parser("treinar", help="treina e valida (não abre o teste)")
    treinar.add_argument("--config", type=Path, default=CONFIGURACAO_PADRAO)
    treinar.add_argument("--nome")
    treinar.add_argument("--dataset")
    treinar.add_argument("--saida")
    treinar.add_argument("--semente", type=int)
    treinar.add_argument("--epocas", type=int, help="substitui epocas_maximas")
    treinar.add_argument("--limite-treino", type=int)
    treinar.add_argument("--limite-validacao", type=int)
    treinar.add_argument("--lambda-area", type=float)
    treinar.add_argument("--versao-modelo")
    treinar.add_argument("--sem-pretreino", action="store_true")

    teste = comandos.add_parser(
        "avaliar-teste", help="mede o conjunto de teste com o melhor checkpoint"
    )
    teste.add_argument("--execucao", type=Path, required=True)
    teste.add_argument("--reavaliar", action="store_true")
    teste.add_argument("--calibracao", type=Path)
    teste.add_argument("--dominio", choices=("sintetico", "real"), default="sintetico")

    comparar = comandos.add_parser("comparar", help="compara duas execuções por época")
    comparar.add_argument("--a", type=Path, required=True)
    comparar.add_argument("--b", type=Path, required=True)
    return parser


def main(argumentos: list[str] | None = None) -> int:
    """Executa um comando e devolve o código de saída."""
    args = _parser().parse_args(argumentos)
    try:
        if args.comando == "gpu":
            from training.treino.loop import informacoes_hardware

            print(json.dumps(informacoes_hardware(), indent=2))
            return 0
        if args.comando == "treinar":
            from training.treino.loop import treinar

            configuracao = carregar_configuracao(args.config).com(
                nome=args.nome,
                dataset=args.dataset,
                saida=args.saida,
                semente_global=args.semente,
                epocas_maximas=args.epocas,
                limite_amostras_treino=args.limite_treino,
                limite_amostras_validacao=args.limite_validacao,
                lambda_area=args.lambda_area,
                versao_modelo=args.versao_modelo,
                encoder_pretreinado=False if args.sem_pretreino else None,
            )
            pasta = treinar(configuracao)
            print(f"execução gravada em {pasta}")
            return 0
        if args.comando == "avaliar-teste":
            from training.treino.avaliacao import avaliar_teste

            opcoes = {"calibracao": args.calibracao} if args.calibracao else {}
            destino = avaliar_teste(
                args.execucao, reavaliar=args.reavaliar, dominio=args.dominio, **opcoes
            )
            print(f"resultado do teste em {destino}")
            return 0
        from training.treino.loop import comparar_execucoes

        print(json.dumps(comparar_execucoes(args.a, args.b), indent=2))
        return 0
    except (ValueError, FileNotFoundError, FileExistsError) as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
