from functools import lru_cache

from pydantic import BaseModel, SecretStr
from pydantic_settings import SettingsConfigDict
from skillcore.config import CoreSettings
from skillcore.logging import LoggingSettings as CoreLoggingSettings


class DiscordSettings(CoreSettings):
    """
    Discord settings loaded from environment/.env.

    Expected keys:
        - DISCORD__TOKEN=...

    Optional keys:
        - DISCORD__GUILD_ID=...
        - DISCORD__SYNC_COMMANDS=...
    """

    token: SecretStr
    guild_id: int | None = None
    sync_commands: bool = False

    model_config = SettingsConfigDict(
        env_prefix="DISCORD__",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class LoggingSettings(CoreLoggingSettings):
    app_name: str = "skillbot"


class SkillForgeSettings(CoreSettings):
    base_url: str
    client_id: str
    client_secret: SecretStr
    timeout_seconds: float = 10.0

    model_config = SettingsConfigDict(
        env_prefix="SKILLFORGE__",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class Settings(BaseModel):
    """
    Pure container: no env loading here.
    Each sub-settings class reads only its own namespace.
    """

    discord: DiscordSettings
    logging: LoggingSettings
    skillforge: SkillForgeSettings


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        discord=DiscordSettings.from_env(),
        logging=LoggingSettings.from_env(),
        skillforge=SkillForgeSettings.from_env(),
    )
