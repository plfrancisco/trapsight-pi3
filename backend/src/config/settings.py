"""Configuração validada do backend, carregada exclusivamente do ambiente."""

from typing import Annotated, Any, Literal, Self

from pydantic import (
    Field,
    SecretStr,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic_settings import (
    BaseSettings,
    NoDecode,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

_ENVIRONMENT_NAMES = {
    "database_url": "DATABASE_URL",
    "model_weights_path": "MODEL_WEIGHTS_PATH",
    "model_version": "MODEL_VERSION",
    "inference_mode": "INFERENCE_MODE",
    "inference_threads": "INFERENCE_THREADS",
    "uploads_dir": "UPLOADS_DIR",
    "storage_backend": "STORAGE_BACKEND",
    "cors_origens": "CORS_ORIGENS",
    "limiar_atencao": "LIMIAR_ATENCAO",
    "limiar_trocar": "LIMIAR_TROCAR",
    "ambiente": "AMBIENTE",
    "cookie_secure": "COOKIE_SECURE",
    "sessao_inatividade_segundos": "SESSAO_INATIVIDADE_SEGUNDOS",
    "sessao_duracao_maxima_segundos": "SESSAO_DURACAO_MAXIMA_SEGUNDOS",
    "sessao_maxima_por_usuario": "SESSAO_MAXIMA_POR_USUARIO",
    "login_falhas_por_conta": "LOGIN_FALHAS_POR_CONTA",
    "login_bloqueio_segundos": "LOGIN_BLOQUEIO_SEGUNDOS",
    "login_falhas_por_ip": "LOGIN_FALHAS_POR_IP",
    "login_janela_segundos": "LOGIN_JANELA_SEGUNDOS",
    "analises_por_minuto": "ANALISES_POR_MINUTO",
    "argon2_memoria_kib": "ARGON2_MEMORIA_KIB",
    "argon2_iteracoes": "ARGON2_ITERACOES",
    "argon2_paralelismo": "ARGON2_PARALELISMO",
}

Ambiente = Literal["desenvolvimento", "homologacao", "producao"]

# Combinações equivalentes de Argon2id recomendadas pelo OWASP (memória em KiB, passadas).
_ARGON2_MINIMOS = ((47104, 1), (19456, 2), (12288, 3), (9216, 4), (7168, 5))


class SettingsConfigurationError(ValueError):
    """Indica uma configuração ausente ou inválida sem revelar seus valores."""


class Settings(BaseSettings):
    """Carrega e valida as variáveis usadas durante a inicialização da API."""

    model_config = SettingsConfigDict(
        case_sensitive=False,
        env_file=None,
        env_prefix="",
        extra="ignore",
    )

    database_url: SecretStr
    model_weights_path: str = "/app/models/checkpoints/latest.pt"
    model_version: str
    inference_mode: Literal["stub", "modelo"] = "modelo"
    inference_threads: int = Field(default=1, ge=1)
    uploads_dir: str
    storage_backend: Literal["filesystem", "database"] = "filesystem"
    cors_origens: Annotated[list[str], NoDecode]
    limiar_atencao: int = 10
    limiar_trocar: int = 20
    ambiente: Ambiente = "desenvolvimento"
    # None significa "decidir pelo ambiente": só desenvolvimento aceita cookie sem Secure.
    cookie_secure: bool | None = None
    sessao_inatividade_segundos: int = Field(default=1800, ge=1)
    sessao_duracao_maxima_segundos: int = Field(default=28800, ge=1)
    sessao_maxima_por_usuario: int = Field(default=5, ge=1)
    login_falhas_por_conta: int = Field(default=5, ge=1)
    login_bloqueio_segundos: int = Field(default=900, ge=1)
    login_falhas_por_ip: int = Field(default=30, ge=1)
    login_janela_segundos: int = Field(default=900, ge=1)
    analises_por_minuto: int = Field(default=30, ge=1)
    argon2_memoria_kib: int = 19456
    argon2_iteracoes: int = 2
    argon2_paralelismo: int = Field(default=1, ge=1)

    def __init__(self, **values: Any) -> None:
        """Converte falhas de validação em mensagens seguras para os logs."""
        try:
            super().__init__(**values)
        except ValidationError as error:
            messages = []
            for issue in error.errors(
                include_input=False,
                include_context=False,
                include_url=False,
            ):
                location = issue.get("loc", ())
                if location:
                    field_name = str(location[0]).lower()
                    variable = _ENVIRONMENT_NAMES.get(field_name, field_name.upper())
                    if issue.get("type") == "missing":
                        message = f"{variable}: variável obrigatória ausente."
                    else:
                        message = f"{variable}: valor inválido."
                else:
                    # Validadores do modelo escrevem mensagens próprias, sem valores.
                    texto = str(issue.get("msg", ""))
                    message = (
                        texto.removeprefix("Value error, ")
                        if issue.get("type") == "value_error" and texto
                        else "Configuração com valores inconsistentes."
                    )
                if message not in messages:
                    messages.append(message)

            raise SettingsConfigurationError(
                "Configuração de ambiente inválida: " + " ".join(messages)
            ) from None

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Restringe a configuração às variáveis exportadas pelo processo."""
        return (env_settings,)

    @field_validator(
        "database_url",
        "model_weights_path",
        "model_version",
        "uploads_dir",
        mode="before",
    )
    @classmethod
    def _validate_required_text(cls, value: Any) -> Any:
        """Rejeita strings vazias antes que cheguem à aplicação."""
        if not isinstance(value, str) or not value.strip():
            raise ValueError("A variável obrigatória deve conter texto.")
        return value

    @field_validator("cors_origens", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: Any) -> list[str]:
        """Divide a lista CSV e exige origens explícitas e sem itens vazios."""
        if isinstance(value, str):
            origins = [origin.strip() for origin in value.split(",")]
        elif isinstance(value, (list, tuple)):
            origins = [origin.strip() for origin in value if isinstance(origin, str)]
        else:
            raise ValueError("CORS_ORIGENS deve ser uma lista separada por vírgula.")

        if not origins or any(not origin for origin in origins):
            raise ValueError("CORS_ORIGENS deve conter ao menos uma origem.")
        if any("*" in origin for origin in origins):
            raise ValueError("CORS_ORIGENS exige origens explícitas.")
        return origins

    @property
    def cookie_seguro(self) -> bool:
        """Indica se o cookie de sessão leva o atributo Secure."""
        if self.cookie_secure is None:
            return self.ambiente != "desenvolvimento"
        return self.cookie_secure

    @property
    def documentacao_habilitada(self) -> bool:
        """A documentação interativa só existe fora de produção."""
        return self.ambiente != "producao"

    @model_validator(mode="after")
    def _validate_ambiente(self) -> Self:
        """Impede combinações inseguras fora do desenvolvimento local."""
        if self.ambiente != "desenvolvimento" and not self.cookie_seguro:
            raise ValueError(
                "COOKIE_SECURE=false só é aceito com AMBIENTE=desenvolvimento."
            )
        if self.ambiente == "producao" and any(
            not origem.startswith("https://") for origem in self.cors_origens
        ):
            raise ValueError(
                "CORS_ORIGENS deve usar somente origens https em produção."
            )
        return self

    @model_validator(mode="after")
    def _validate_argon2(self) -> Self:
        """Exige parâmetros de Argon2id iguais ou acima do mínimo do OWASP."""
        if not any(
            self.argon2_memoria_kib >= memoria and self.argon2_iteracoes >= iteracoes
            for memoria, iteracoes in _ARGON2_MINIMOS
        ):
            raise ValueError(
                "ARGON2_MEMORIA_KIB e ARGON2_ITERACOES ficam abaixo do mínimo do OWASP "
                "(19456 KiB com 2 iterações, ou combinação equivalente)."
            )
        return self

    @model_validator(mode="after")
    def _validate_sessao(self) -> Self:
        """A duração absoluta nunca pode ser menor que o prazo de inatividade."""
        if self.sessao_duracao_maxima_segundos < self.sessao_inatividade_segundos:
            raise ValueError(
                "SESSAO_DURACAO_MAXIMA_SEGUNDOS deve ser maior ou igual a "
                "SESSAO_INATIVIDADE_SEGUNDOS."
            )
        return self

    @model_validator(mode="after")
    def _validate_thresholds(self) -> Self:
        """Garante que os limiares estejam em ordem e dentro da escala percentual."""
        if not 0 < self.limiar_atencao < self.limiar_trocar <= 100:
            raise ValueError(
                "LIMIAR_ATENCAO deve ser menor que LIMIAR_TROCAR, entre 0 e 100."
            )
        return self
