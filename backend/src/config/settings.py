"""Configuração validada do backend, carregada exclusivamente do ambiente."""

from typing import Annotated, Any, Self

from pydantic import SecretStr, ValidationError, field_validator, model_validator
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
    "uploads_dir": "UPLOADS_DIR",
    "cors_origens": "CORS_ORIGENS",
    "limiar_atencao": "LIMIAR_ATENCAO",
    "limiar_trocar": "LIMIAR_TROCAR",
}


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
    model_weights_path: str
    model_version: str
    uploads_dir: str
    cors_origens: Annotated[list[str], NoDecode]
    limiar_atencao: int = 40
    limiar_trocar: int = 70

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
                    message = "LIMIAR_ATENCAO e LIMIAR_TROCAR: valores inconsistentes."
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

    @model_validator(mode="after")
    def _validate_thresholds(self) -> Self:
        """Garante que os limiares estejam em ordem e dentro da escala percentual."""
        if not 0 < self.limiar_atencao < self.limiar_trocar <= 100:
            raise ValueError(
                "LIMIAR_ATENCAO deve ser menor que LIMIAR_TROCAR, entre 0 e 100."
            )
        return self
