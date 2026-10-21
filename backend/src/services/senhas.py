"""Política, hash e verificação de senhas (Argon2id)."""

from __future__ import annotations

import re
import secrets
import unicodedata
from functools import lru_cache
from pathlib import Path

from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError
from pwdlib.hashers.argon2 import Argon2Hasher

TAMANHO_MINIMO_SENHA = 15
TAMANHO_MAXIMO_SENHA = 128
NOME_DO_PRODUTO = "trapsight"

_ARQUIVO_BLOQUEADAS = Path(__file__).with_name("senhas_bloqueadas.txt")
# Palavras que, sozinhas, repetidas ou seguidas de números/símbolos, não protegem nada.
_PALAVRAS_BASE = (
    "password",
    "passw0rd",
    "senha",
    "admin",
    "administrator",
    "qwerty",
    "welcome",
    "letmein",
    "iloveyou",
    "brasil",
    "trapsight",
    "monkey",
    "dragon",
    "football",
    "master",
    "login",
    "teste",
    "mudar",
    "changeme",
    "secret",
    "minhasenha",
)
_SO_PALAVRAS_BASE = re.compile("(?:" + "|".join(map(re.escape, _PALAVRAS_BASE)) + ")+")
_PADRAO_REPETIDO = re.compile(r"(.{1,4})\1+")


class SenhaFraca(ValueError):
    """Indica que a senha viola a política; o motivo nunca contém a senha."""

    def __init__(self, motivo: str) -> None:
        """Guarda o motivo estável da recusa.

        Args:
            motivo: um de `curta`, `longa`, `comum`, `trivial` ou `contextual`.
        """
        super().__init__(motivo)
        self.motivo = motivo


def normalizar_senha(senha: str) -> str:
    """Aplica a normalização NFC antes de medir, validar ou calcular o hash.

    Args:
        senha: senha como digitada.

    Returns:
        A senha em NFC, para que a mesma frase funcione em qualquer teclado.
    """
    return unicodedata.normalize("NFC", senha)


@lru_cache(maxsize=1)
def _senhas_bloqueadas() -> frozenset[str]:
    """Carrega a lista de senhas comuns uma única vez, sem distinção de caixa."""
    linhas = _ARQUIVO_BLOQUEADAS.read_text(encoding="utf-8").splitlines()
    return frozenset(
        linha.strip().casefold()
        for linha in linhas
        if linha.strip() and not linha.lstrip().startswith("#")
    )


def _alfanumerico(texto: str) -> str:
    return "".join(caractere for caractere in texto if caractere.isalnum())


def _sequencia_simples(texto: str) -> bool:
    """Detecta um só caractere repetido ou sequência contínua crescente/decrescente."""
    if len(texto) < 2:
        return False
    if len(set(texto)) == 1:
        return True
    passos = {ord(b) - ord(a) for a, b in zip(texto, texto[1:])}
    return passos in ({1}, {-1})


def validar_politica(senha: str, *, email: str, nome: str = "") -> None:
    """Confere a senha contra a política de login.md (NIST SP 800-63B-4).

    Não há regra de composição (maiúscula, número, símbolo): comprimento e uma
    lista de bloqueio protegem mais do que complexidade.

    Args:
        senha: senha como digitada (a normalização NFC é aplicada aqui).
        email: e-mail da conta, para recusar senhas derivadas dele.
        nome: nome do usuário, para recusar senhas derivadas dele.

    Raises:
        SenhaFraca: se a senha violar a política.
    """
    texto = normalizar_senha(senha)
    tamanho = len(texto)  # cada ponto de código conta como um caractere
    if tamanho < TAMANHO_MINIMO_SENHA:
        raise SenhaFraca("curta")
    if tamanho > TAMANHO_MAXIMO_SENHA:
        raise SenhaFraca("longa")

    baixa = texto.casefold()
    if baixa in _senhas_bloqueadas():
        raise SenhaFraca("comum")
    if _sequencia_simples(baixa) or _PADRAO_REPETIDO.fullmatch(baixa):
        raise SenhaFraca("trivial")
    letras = "".join(caractere for caractere in baixa if caractere.isalpha())
    if letras and _SO_PALAVRAS_BASE.fullmatch(letras):
        raise SenhaFraca("comum")

    alfanumerica = _alfanumerico(baixa)
    local = _alfanumerico(email.split("@")[0].casefold())
    partes_do_nome = [
        parte for parte in re.split(r"\W+", nome.casefold()) if len(parte) >= 4
    ]
    if (
        NOME_DO_PRODUTO in alfanumerica
        or email.casefold() in baixa
        or (len(local) >= 4 and local in alfanumerica)
        or any(parte in alfanumerica for parte in partes_do_nome)
    ):
        raise SenhaFraca("contextual")


class ServicoDeSenhas:
    """Gera e verifica hashes Argon2id com os parâmetros configurados."""

    def __init__(self, *, memoria_kib: int, iteracoes: int, paralelismo: int) -> None:
        """Cria o hasher e um hash fictício com os mesmos parâmetros.

        Args:
            memoria_kib: memória do Argon2id, em KiB.
            iteracoes: número de passadas do Argon2id.
            paralelismo: grau de paralelismo do Argon2id.
        """
        self._hasher = PasswordHash(
            (
                Argon2Hasher(
                    time_cost=iteracoes,
                    memory_cost=memoria_kib,
                    parallelism=paralelismo,
                ),
            )
        )
        # Usado quando a conta não existe, para o tempo de resposta não revelar isso.
        self._hash_ficticio = self._hasher.hash(secrets.token_urlsafe(24))

    def gerar_hash(self, senha: str) -> str:
        """Calcula o hash PHC de uma senha já aprovada pela política.

        Args:
            senha: senha como digitada.

        Returns:
            String PHC do Argon2id, com sal único.
        """
        return self._hasher.hash(normalizar_senha(senha))

    def verificar(self, senha: str, hash_armazenado: str) -> tuple[bool, str | None]:
        """Confere a senha e informa se o hash deve ser regravado.

        Args:
            senha: senha como digitada.
            hash_armazenado: string PHC guardada para a conta.

        Returns:
            Se a senha confere e, quando os parâmetros mudaram, o novo hash.
        """
        try:
            return self._hasher.verify_and_update(
                normalizar_senha(senha), hash_armazenado
            )
        except UnknownHashError:
            return False, None

    def verificar_contra_ficticio(self, senha: str) -> None:
        """Gasta o mesmo tempo de uma verificação real quando a conta não existe.

        Args:
            senha: senha como digitada; o resultado é sempre descartado.
        """
        self._hasher.verify(normalizar_senha(senha), self._hash_ficticio)
