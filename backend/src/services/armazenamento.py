"""Grava arquivos de uma análise sob um diretório protegido por UUID."""

import os
import shutil
from pathlib import Path
from uuid import UUID, uuid4


def gravar_imagem_original(
    diretorio_uploads: str | Path,
    analise_id: UUID,
    conteudo: bytes,
    extensao: str,
) -> str:
    """Grava a imagem original de forma atômica e devolve o caminho relativo.

    Args:
        diretorio_uploads: diretório raiz definido na configuração da aplicação.
        analise_id: UUID criado pelo servidor para a análise.
        conteudo: imagem validada em bytes.
        extensao: extensão derivada do formato real da imagem.

    Returns:
        Caminho POSIX relativo que pode ser persistido no banco.
    """
    if extensao not in {"jpg", "png"}:
        raise ValueError("A extensão da imagem deve refletir um formato permitido.")
    return _gravar_arquivo_atomico(
        diretorio_uploads,
        analise_id,
        f"original.{extensao}",
        conteudo,
    )


def gravar_mascara(
    diretorio_uploads: str | Path,
    analise_id: UUID,
    conteudo: bytes,
) -> str:
    """Grava a máscara PNG ao lado da imagem original de forma atômica.

    Args:
        diretorio_uploads: diretório raiz definido na configuração da aplicação.
        analise_id: UUID criado pelo servidor para a análise.
        conteudo: máscara PNG produzida pelo inferidor.

    Returns:
        Caminho POSIX relativo ao diretório de uploads.
    """
    return _gravar_arquivo_atomico(
        diretorio_uploads,
        analise_id,
        "mascara.png",
        conteudo,
    )


def remover_arquivos_analise(diretorio_uploads: str | Path, analise_id: UUID) -> None:
    """Remove a pasta da análise após uma falha posterior à gravação.

    Args:
        diretorio_uploads: diretório raiz definido na configuração da aplicação.
        analise_id: UUID criado pelo servidor para a análise.
    """
    raiz = Path(diretorio_uploads).resolve()
    pasta = raiz / str(analise_id)
    _validar_destino(raiz, pasta)
    if pasta.is_symlink():
        pasta.unlink()
    elif pasta.exists():
        shutil.rmtree(pasta)


def _gravar_arquivo_atomico(
    diretorio_uploads: str | Path,
    analise_id: UUID,
    nome_arquivo: str,
    conteudo: bytes,
) -> str:
    """Cria um arquivo temporário na pasta final e o publica com rename atômico."""
    raiz = Path(diretorio_uploads).resolve()
    raiz.mkdir(parents=True, exist_ok=True)
    pasta = raiz / str(analise_id)
    _validar_destino(raiz, pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    _validar_destino(raiz, pasta)

    destino = pasta / nome_arquivo
    _validar_destino(raiz, destino)
    temporario = pasta / f".{uuid4().hex}.tmp"
    _validar_destino(raiz, temporario)
    try:
        with temporario.open("xb") as arquivo:
            arquivo.write(conteudo)
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(temporario, destino)
    finally:
        temporario.unlink(missing_ok=True)

    return destino.relative_to(raiz).as_posix()


def _validar_destino(raiz: Path, destino: Path) -> None:
    """Exige que o caminho resolvido continue dentro do diretório configurado."""
    raiz_resolvida = raiz.resolve()
    destino_resolvido = destino.resolve()
    if not destino_resolvido.is_relative_to(raiz_resolvida):
        raise ValueError("O caminho do arquivo precisa permanecer em UPLOADS_DIR.")
