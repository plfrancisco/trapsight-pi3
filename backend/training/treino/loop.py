"""Loop de treino, validação por época e avaliação final do teste.

O conjunto de teste só é lido por `avaliar_teste`, uma vez por checkpoint
(treino_spec.md, seção 6.2). O loop de treino nunca o abre.
"""

from __future__ import annotations

import csv
import json
import math
import os
import platform
import random
import time
from collections.abc import Callable
from contextlib import nullcontext
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader

from training.treino.aumentos import transformacao_avaliacao, transformacao_treino
from training.treino.configuracao import Configuracao
from training.treino.dados import (
    DatasetSegmentacao,
    amostrar,
    contar_pixels_por_classe,
    derivar_semente,
    exigir_dataset_valido,
    hash_arquivo,
    ler_dataset,
    pesos_de_classe,
    verificar_mascaras,
)
from training.treino.metricas import AcumuladorMetricas
from training.treino.modelo import (
    carregar_checkpoint,
    colocar_em_treino,
    congelar_encoder,
    criar_modelo,
    gravar_checkpoint,
    grupos_de_parametros,
)
from training.treino.perda import PerdaSegmentacao
from training.treino.selecao import SelecaoMelhorPonto, chave_de_selecao

BIBLIOTECAS = (
    "torch",
    "torchvision",
    "segmentation-models-pytorch",
    "albumentations",
    "torchmetrics",
    "numpy",
    "opencv-python-headless",
    "pillow",
)
CANDIDATOS_LOTE = (4, 2, 1)
FOLGA_VRAM = 0.75
COLUNAS_CSV = (
    "epoca",
    "tempo_s",
    "lr_decoder",
    "perda_treino",
    "perda_ce",
    "perda_dice",
    "perda_area",
    "perda_validacao",
    "erro_percentual_medio_pp",
    "dice_coberta",
    "dice_medio",
    "acuracia_status",
    "trocar_como_ok",
    "falhas_deteccao_placa",
    "vram_pico_mb",
    "melhor_ponto",
)

Registro = Callable[[str], None]


def configurar_determinismo(semente: int) -> None:
    """Fixa as sementes e pede algoritmos determinísticos quando existirem."""
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    random.seed(semente)
    np.random.seed(semente % (2**32))
    torch.manual_seed(semente)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(semente)
    torch.use_deterministic_algorithms(True, warn_only=True)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True


def versoes_bibliotecas() -> dict[str, str]:
    """Versões das bibliotecas relevantes, para o registro da execução."""
    versoes = {"python": platform.python_version()}
    for nome in BIBLIOTECAS:
        try:
            versoes[nome] = metadata.version(nome)
        except metadata.PackageNotFoundError:
            versoes[nome] = "ausente"
    return versoes


def informacoes_hardware() -> dict[str, Any]:
    """GPU, memória de vídeo e versões de CUDA, quando houver."""
    if not torch.cuda.is_available():
        return {"dispositivo": "cpu"}
    propriedades = torch.cuda.get_device_properties(0)
    return {
        "dispositivo": "cuda",
        "gpu": propriedades.name,
        "vram_total_mb": round(propriedades.total_memory / 2**20),
        "cuda": torch.version.cuda,
        "cudnn": torch.backends.cudnn.version(),
    }


def gravar_json(caminho: Path, dados: dict[str, Any]) -> None:
    """Grava JSON de forma atômica (arquivo temporário e renomeação)."""
    temporario = caminho.with_suffix(caminho.suffix + ".tmp")
    temporario.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporario.replace(caminho)


def descobrir_lote_por_passo(
    configuracao: Configuracao, perda: nn.Module, dispositivo: torch.device
) -> int:
    """Maior lote que cabe na VRAM livre com folga, por teste de passo completo.

    O passo de teste faz a propagação, a perda, a retropropagação e um passo do
    AdamW, porque o estado do otimizador também ocupa memória. O pico é
    comparado com a memória **livre** no início, e não com a total: o sistema e
    outros programas já usam parte da GPU. Usa um modelo descartável (sem pesos
    pré-treinados) para não alterar as estatísticas do modelo real. Em CPU
    devolve um lote pequeno fixo. Lança RuntimeError se nenhum candidato couber
    no orçamento de VRAM, em vez de iniciar um treino inviável.
    """
    if configuracao.batch_por_passo != "auto":
        return int(configuracao.batch_por_passo)
    if dispositivo.type != "cuda":
        return min(2, configuracao.batch_efetivo)

    torch.cuda.empty_cache()
    livre, _ = torch.cuda.mem_get_info(dispositivo)
    orcamento = FOLGA_VRAM * livre
    sonda = criar_modelo(configuracao.com(encoder_pretreinado=False)).to(dispositivo)
    sonda.to(memory_format=torch.channels_last)
    colocar_em_treino(sonda, configuracao.bn_encoder_congelado)
    otimizador = torch.optim.AdamW(sonda.parameters(), lr=1e-6)
    escolhido = None
    for candidato in CANDIDATOS_LOTE:
        if candidato > configuracao.batch_efetivo:
            continue
        torch.cuda.reset_peak_memory_stats(dispositivo)
        try:
            entrada = torch.randn(
                candidato,
                3,
                configuracao.altura,
                configuracao.largura,
                device=dispositivo,
            ).contiguous(memory_format=torch.channels_last)
            alvo = torch.randint(
                0,
                3,
                (candidato, configuracao.altura, configuracao.largura),
                device=dispositivo,
            )
            with torch.autocast("cuda", enabled=configuracao.precisao_mista):
                logits = sonda(entrada)
            perda(logits, alvo).total.backward()
            otimizador.step()
            pico = torch.cuda.max_memory_reserved(dispositivo)
        except torch.cuda.OutOfMemoryError:
            pico = None
        finally:
            otimizador.zero_grad(set_to_none=True)
            entrada = alvo = logits = None  # libera os tensores do candidato
            torch.cuda.empty_cache()
        if pico is not None and pico <= orcamento:
            escolhido = candidato
            break
    del sonda, otimizador
    torch.cuda.empty_cache()
    if escolhido is None:
        raise RuntimeError(
            "Memória de vídeo insuficiente: nem o lote 1 cabe no orçamento de "
            "VRAM livre com folga. Reduza a resolução somente no teste de fumaça "
            "E0, ative gradient checkpointing no encoder ou use outra GPU."
        )
    return escolhido


def _atualizar_lr(
    otimizador: torch.optim.Optimizer,
    configuracao: Configuracao,
    passo: int,
    passos_aquecimento: int,
    passos_totais: int,
) -> float:
    """Aquecimento linear e depois decaimento por cosseno até o piso."""
    if passos_aquecimento > 0 and passo < passos_aquecimento:
        fator = (passo + 1) / passos_aquecimento
    else:
        restantes = max(passos_totais - passos_aquecimento, 1)
        progresso = min((passo - passos_aquecimento) / restantes, 1.0)
        fator = 0.5 * (1.0 + math.cos(math.pi * progresso))
    for grupo in otimizador.param_groups:
        grupo["lr"] = max(configuracao.lr_minimo, grupo["base_lr"] * fator)
    return otimizador.param_groups[-1]["lr"]


def _criar_loader(
    dataset: DatasetSegmentacao,
    tamanho_lote: int,
    configuracao: Configuracao,
    embaralhar: bool,
    epoca: int,
    dispositivo: torch.device,
) -> DataLoader:
    gerador = None
    if embaralhar:
        gerador = torch.Generator()
        gerador.manual_seed(derivar_semente(configuracao.semente_global, epoca, 0))
    return DataLoader(
        dataset,
        batch_size=tamanho_lote,
        shuffle=embaralhar,
        generator=gerador,
        drop_last=embaralhar,
        num_workers=configuracao.num_workers,
        pin_memory=dispositivo.type == "cuda",
        persistent_workers=False,
    )


def _contexto_amp(configuracao: Configuracao, dispositivo: torch.device):
    if configuracao.precisao_mista and dispositivo.type == "cuda":
        return torch.autocast("cuda")
    return nullcontext()


def _exigir_perda_finita(valor: float, contexto: str) -> None:
    if not math.isfinite(valor):
        raise FloatingPointError(f"Perda não finita em {contexto}: {valor}.")


@torch.no_grad()
def validar(
    modelo: nn.Module,
    loader: DataLoader,
    perda: nn.Module,
    configuracao: Configuracao,
    dispositivo: torch.device,
) -> tuple[dict[str, Any], float]:
    """Devolve métricas e perda média; lança FloatingPointError se não for finita."""
    modelo.eval()
    acumulador = AcumuladorMetricas()
    soma_perda, lotes = 0.0, 0
    amostras = loader.dataset.amostras
    for imagens, mascaras, indices in loader:
        imagens = imagens.to(dispositivo).contiguous(memory_format=torch.channels_last)
        mascaras = mascaras.to(dispositivo)
        with _contexto_amp(configuracao, dispositivo):
            logits = modelo(imagens)
        valor_perda = float(perda(logits, mascaras).total)
        _exigir_perda_finita(valor_perda, f"validação, lote {lotes + 1}")
        soma_perda += valor_perda
        _exigir_perda_finita(soma_perda, "validação, perda acumulada")
        lotes += 1
        selecionadas = [amostras[int(i)] for i in indices]
        acumulador.atualizar(
            logits.float(),
            mascaras,
            [a.idade_dias for a in selecionadas],
            [a.dominante_cor for a in selecionadas],
        )
    return acumulador.resultado(), soma_perda / max(lotes, 1)


def treinar(
    configuracao: Configuracao,
    registro: Registro = print,
    dispositivo: torch.device | None = None,
) -> Path:
    """Treina e devolve a pasta; registra e propaga perdas não finitas como erro."""
    configuracao.validar()
    configurar_determinismo(configuracao.semente_global)
    dispositivo = dispositivo or torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )

    info = ler_dataset(Path(configuracao.dataset))
    exigir_dataset_valido(info)
    amostras_treino = amostrar(
        info.do_conjunto("treino"),
        configuracao.limite_amostras_treino,
        configuracao.semente_global,
    )
    amostras_validacao = amostrar(
        info.do_conjunto("validacao"),
        configuracao.limite_amostras_validacao,
        configuracao.semente_global,
    )
    contagens = contar_pixels_por_classe(amostras_treino)
    pesos = pesos_de_classe(
        contagens, configuracao.peso_expoente, configuracao.peso_teto
    )
    perda = PerdaSegmentacao(
        torch.tensor(pesos, dtype=torch.float32), configuracao.lambda_area
    ).to(dispositivo)

    instante = datetime.now(timezone.utc)
    pasta = Path(configuracao.saida) / f"{instante:%Y%m%d-%H%M%S}-{configuracao.nome}"
    pasta.mkdir(parents=True, exist_ok=False)

    lote_passo = descobrir_lote_por_passo(configuracao, perda, dispositivo)
    acumulo = max(1, math.ceil(configuracao.batch_efetivo / lote_passo))
    registro(
        f"dispositivo={dispositivo.type} lote_por_passo={lote_passo} "
        f"acumulo={acumulo} lote_efetivo={lote_passo * acumulo}"
    )

    modelo = criar_modelo(configuracao).to(dispositivo)
    modelo.to(memory_format=torch.channels_last)
    otimizador = torch.optim.AdamW(
        grupos_de_parametros(modelo, configuracao),
        weight_decay=configuracao.weight_decay,
    )
    escalador = torch.amp.GradScaler(
        "cuda", enabled=configuracao.precisao_mista and dispositivo.type == "cuda"
    )

    ds_treino = DatasetSegmentacao(
        amostras_treino,
        transformacao_treino(),
        configuracao.semente_global,
        reprodutivel=True,
    )
    ds_validacao = DatasetSegmentacao(
        amostras_validacao, transformacao_avaliacao(), configuracao.semente_global
    )
    passos_por_epoca = max(len(amostras_treino) // lote_passo // acumulo, 1)
    passos_totais = configuracao.epocas_maximas * passos_por_epoca
    passos_aquecimento = configuracao.aquecimento_epocas * passos_por_epoca

    execucao: dict[str, Any] = {
        "identificador": pasta.name,
        "iniciada_em": instante.isoformat(),
        "commit_git": _commit_git(),
        "semente_global": configuracao.semente_global,
        "dataset": {
            "caminho": str(info.raiz),
            "hash_metadados_sha256": info.hash_metadados,
            "semente_global_geracao": info.semente_global,
            "amostras_treino": len(amostras_treino),
            "amostras_validacao": len(amostras_validacao),
            "sementes_por_conjunto": {
                k: v for k, v in info.sementes_por_conjunto().items() if k != "teste"
            },
        },
        "configuracao": {
            **configuracao.como_dicionario(),
            "batch_por_passo_efetivo": lote_passo,
            "acumulo_gradiente": acumulo,
            "batch_efetivo_real": lote_passo * acumulo,
            "pesos_de_classe": [float(p) for p in pesos],
            "pixels_por_classe_treino": [int(c) for c in contagens],
        },
        "bibliotecas": versoes_bibliotecas(),
        "hardware": informacoes_hardware(),
    }
    gravar_json(pasta / "execucao.json", execucao)

    arquivo_csv = (pasta / "metricas_por_epoca.csv").open(
        "w", newline="", encoding="utf-8"
    )
    escritor = csv.DictWriter(arquivo_csv, fieldnames=COLUNAS_CSV)
    escritor.writeheader()
    selecao = SelecaoMelhorPonto(configuracao.paciencia, configuracao.melhora_minima_pp)
    melhor: dict[str, Any] = {}
    passo, inicio = 0, time.monotonic()
    parou_antes, epocas_executadas = False, 0

    try:
        for epoca in range(1, configuracao.epocas_maximas + 1):
            inicio_epoca = time.monotonic()
            congelar_encoder(modelo, epoca <= configuracao.congelar_encoder_epocas)
            colocar_em_treino(modelo, configuracao.bn_encoder_congelado)
            ds_treino.epoca = epoca
            loader = _criar_loader(
                ds_treino, lote_passo, configuracao, True, epoca, dispositivo
            )
            if dispositivo.type == "cuda":
                torch.cuda.reset_peak_memory_stats(dispositivo)
            somas = {"total": 0.0, "ce": 0.0, "dice": 0.0, "area": 0.0}
            lotes = 0
            otimizador.zero_grad(set_to_none=True)
            lr_atual = otimizador.param_groups[-1]["lr"]
            for indice_lote, (imagens, mascaras, _) in enumerate(loader):
                imagens = imagens.to(dispositivo, non_blocking=True).contiguous(
                    memory_format=torch.channels_last
                )
                mascaras = mascaras.to(dispositivo, non_blocking=True)
                with _contexto_amp(configuracao, dispositivo):
                    logits = modelo(imagens)
                resultado = perda(logits, mascaras)
                # A verificação precede a retropropagação para não contaminar
                # os pesos e o estado do otimizador com uma perda inválida.
                _exigir_perda_finita(
                    float(resultado.total.detach()),
                    f"treino, época {epoca}, lote {indice_lote + 1}",
                )
                escalador.scale(resultado.total / acumulo).backward()
                for chave, valor in (
                    ("total", resultado.total),
                    ("ce", resultado.ce),
                    ("dice", resultado.dice),
                    ("area", resultado.area),
                ):
                    somas[chave] += float(valor.detach())
                lotes += 1
                if (indice_lote + 1) % acumulo == 0:
                    escalador.unscale_(otimizador)
                    nn.utils.clip_grad_norm_(
                        [p for p in modelo.parameters() if p.requires_grad],
                        configuracao.corte_gradiente,
                    )
                    lr_atual = _atualizar_lr(
                        otimizador,
                        configuracao,
                        passo,
                        passos_aquecimento,
                        passos_totais,
                    )
                    escalador.step(otimizador)
                    escalador.update()
                    otimizador.zero_grad(set_to_none=True)
                    passo += 1

            _exigir_perda_finita(
                somas["total"], f"treino, época {epoca}, perda acumulada"
            )
            pico = (
                torch.cuda.max_memory_allocated(dispositivo) / 2**20
                if dispositivo.type == "cuda"
                else 0.0
            )
            loader_validacao = _criar_loader(
                ds_validacao, lote_passo, configuracao, False, epoca, dispositivo
            )
            metricas, perda_validacao = validar(
                modelo, loader_validacao, perda, configuracao, dispositivo
            )
            # Nenhuma decisão de seleção ou gravação pode usar uma época
            # cuja validação tenha falhado numericamente.
            _exigir_perda_finita(perda_validacao, f"validação, época {epoca}")
            decisao = selecao.atualizar(metricas)
            epocas_executadas = epoca

            if decisao.melhor_ponto:
                versao = gravar_checkpoint(modelo, configuracao, pasta / "melhor.pt")
                melhor = {
                    "epoca": epoca,
                    "chave_de_selecao": list(chave_de_selecao(metricas)),
                    "metricas_validacao": metricas,
                    "checkpoint": "melhor.pt",
                    "modelo_versao": versao,
                }
            if decisao.melhor_por_dice:
                gravar_checkpoint(modelo, configuracao, pasta / "melhor_dice.pt")
            gravar_checkpoint(modelo, configuracao, pasta / "ultimo.pt")

            linha = {
                "epoca": epoca,
                "tempo_s": round(time.monotonic() - inicio_epoca, 1),
                "lr_decoder": f"{lr_atual:.6g}",
                "perda_treino": round(somas["total"] / max(lotes, 1), 5),
                "perda_ce": round(somas["ce"] / max(lotes, 1), 5),
                "perda_dice": round(somas["dice"] / max(lotes, 1), 5),
                "perda_area": round(somas["area"] / max(lotes, 1), 5),
                "perda_validacao": round(perda_validacao, 5),
                "erro_percentual_medio_pp": round(
                    metricas["erro_percentual_medio_pp"], 4
                ),
                "dice_coberta": round(metricas["dice_coberta"], 5),
                "dice_medio": round(metricas["dice_medio"], 5),
                "acuracia_status": round(metricas["acuracia_status"], 4),
                "trocar_como_ok": metricas["trocar_como_ok"],
                "falhas_deteccao_placa": metricas["falhas_deteccao_placa"],
                "vram_pico_mb": round(pico),
                "melhor_ponto": int(decisao.melhor_ponto),
            }
            escritor.writerow(linha)
            arquivo_csv.flush()
            with (pasta / "metricas_validacao.jsonl").open(
                "a", encoding="utf-8"
            ) as saida:
                saida.write(
                    json.dumps({"epoca": epoca, **metricas}, ensure_ascii=False) + "\n"
                )
            registro(
                f"epoca {epoca:>2} | treino {linha['perda_treino']:.4f} | "
                f"val erro {linha['erro_percentual_medio_pp']:.2f} pp | "
                f"dice {linha['dice_coberta']:.4f} | status {linha['acuracia_status']:.3f} | "
                f"{linha['tempo_s']:.0f}s{' *' if decisao.melhor_ponto else ''}"
            )
            if decisao.parar:
                parou_antes = True
                registro("parada antecipada")
                break
    except FloatingPointError as erro:
        mensagem = f"Treino interrompido na época {epoca}: {erro}"
        execucao.update(
            status="abortada",
            erro={"tipo": type(erro).__name__, "mensagem": mensagem, "epoca": epoca},
            finalizada_em=datetime.now(timezone.utc).isoformat(),
            tempo_total_s=round(time.monotonic() - inicio, 1),
            epocas_executadas=epocas_executadas,
            melhor_ponto=melhor,
            modelo_versao=melhor.get("modelo_versao"),
        )
        gravar_json(pasta / "execucao.json", execucao)
        raise FloatingPointError(mensagem) from erro
    except torch.cuda.OutOfMemoryError as erro:
        raise RuntimeError(
            "Memória de vídeo insuficiente. Defina um batch_por_passo menor na "
            "configuração (o lote efetivo é mantido por acúmulo de gradiente) e "
            "feche programas que usem a GPU."
        ) from erro
    finally:
        arquivo_csv.close()

    execucao["finalizada_em"] = datetime.now(timezone.utc).isoformat()
    execucao["tempo_total_s"] = round(time.monotonic() - inicio, 1)
    execucao["epocas_executadas"] = epocas_executadas
    execucao["parada_antecipada"] = parou_antes
    execucao["melhor_ponto"] = melhor
    execucao["modelo_versao"] = melhor.get("modelo_versao")
    gravar_json(pasta / "execucao.json", execucao)
    return pasta


def _commit_git() -> dict[str, Any]:
    """Commit atual e se havia alterações não commitadas, quando há Git."""
    import subprocess

    def executar(*args: str) -> str:
        return subprocess.run(
            ["git", *args], capture_output=True, text=True, timeout=10, check=True
        ).stdout.strip()

    try:
        return {
            "commit": executar("rev-parse", "HEAD"),
            "alteracoes_nao_commitadas": bool(executar("status", "--porcelain")),
        }
    except (OSError, subprocess.SubprocessError):
        return {"commit": None, "alteracoes_nao_commitadas": None}


def avaliar_teste(
    pasta_execucao: Path,
    registro: Registro = print,
    reavaliar: bool = False,
    dispositivo: torch.device | None = None,
) -> Path:
    """Mede o conjunto de teste com o melhor checkpoint e grava o resultado.

    O teste é medido uma vez por checkpoint: reavaliar exige `reavaliar=True` e
    cria um novo arquivo, de modo que o histórico fica visível.
    """
    pasta = Path(pasta_execucao)
    execucao = json.loads((pasta / "execucao.json").read_text(encoding="utf-8"))
    checkpoint = pasta / "melhor.pt"
    hash_checkpoint = hash_arquivo(checkpoint)
    destino = pasta / f"avaliacao_teste_{hash_checkpoint[:8]}.json"
    if destino.exists() and not reavaliar:
        raise FileExistsError(
            f"O teste deste checkpoint já foi medido ({destino.name}). "
            "Use --reavaliar para registrar uma nova medição."
        )
    if destino.exists():
        destino = destino.with_name(
            f"avaliacao_teste_{hash_checkpoint[:8]}_{datetime.now(timezone.utc):%Y%m%d%H%M%S}.json"
        )

    dados_config = {
        k: v
        for k, v in execucao["configuracao"].items()
        if k in Configuracao.__dataclass_fields__
    }
    configuracao = Configuracao(**dados_config)
    dispositivo = dispositivo or torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )
    info = ler_dataset(Path(execucao["dataset"]["caminho"]))
    if info.hash_metadados != execucao["dataset"]["hash_metadados_sha256"]:
        raise ValueError("Os metadados do dataset mudaram desde o treino.")

    teste = info.do_conjunto("teste")
    problemas = verificar_mascaras(teste)
    if problemas:
        raise ValueError(" ".join(problemas))

    modelo, _ = carregar_checkpoint(checkpoint, str(dispositivo))
    modelo.to(memory_format=torch.channels_last)
    pesos = torch.tensor(
        execucao["configuracao"]["pesos_de_classe"], dtype=torch.float32
    )
    perda = PerdaSegmentacao(pesos, configuracao.lambda_area).to(dispositivo)
    lote = int(execucao["configuracao"]["batch_por_passo_efetivo"])
    loader = _criar_loader(
        DatasetSegmentacao(
            teste, transformacao_avaliacao(), configuracao.semente_global
        ),
        lote,
        configuracao,
        False,
        0,
        dispositivo,
    )
    metricas, perda_teste = validar(modelo, loader, perda, configuracao, dispositivo)
    resultado = {
        "execucao": execucao["identificador"],
        "avaliado_em": datetime.now(timezone.utc).isoformat(),
        "checkpoint_sha256": hash_checkpoint,
        "modelo_versao": execucao.get("modelo_versao"),
        "hash_metadados_sha256": info.hash_metadados,
        "amostras_teste": len(teste),
        "perda_teste": perda_teste,
        "metricas": metricas,
    }
    gravar_json(destino, resultado)
    registro(
        f"teste: erro {metricas['erro_percentual_medio_pp']:.2f} pp | "
        f"dice coberta {metricas['dice_coberta']:.4f} | "
        f"status {metricas['acuracia_status']:.3f} | trocar->ok {metricas['trocar_como_ok']}"
    )
    return destino


def comparar_execucoes(pasta_a: Path, pasta_b: Path) -> dict[str, Any]:
    """Diferença máxima entre duas execuções, por época, no erro percentual."""

    def ler(pasta: Path) -> list[dict[str, Any]]:
        linhas = (Path(pasta) / "metricas_validacao.jsonl").read_text(encoding="utf-8")
        return [json.loads(linha) for linha in linhas.splitlines() if linha.strip()]

    a, b = ler(pasta_a), ler(pasta_b)
    epocas = min(len(a), len(b))
    diferencas = [
        abs(a[i]["erro_percentual_medio_pp"] - b[i]["erro_percentual_medio_pp"])
        for i in range(epocas)
    ]
    return {
        "epocas_comparadas": epocas,
        "epocas_a": len(a),
        "epocas_b": len(b),
        "diferenca_maxima_erro_pp": max(diferencas) if diferencas else None,
        "diferencas_por_epoca_pp": diferencas,
    }
