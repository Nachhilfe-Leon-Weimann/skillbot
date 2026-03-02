from functools import lru_cache

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from skillcore.config import DatabaseSettings, LoggingSettings


class DiscordRoleIds(BaseModel):
    student: int | None = None
    teacher: int | None = None
    admin: int | None = None


class DiscordRoleNames(BaseModel):
    student: str = "Schüler"
    teacher: str = "Lehrer"
    admin: str = "Admin"


class DiscordSettings(BaseSettings):
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
    role_ids: DiscordRoleIds = Field(default_factory=DiscordRoleIds)
    role_names: DiscordRoleNames = Field(default_factory=DiscordRoleNames)

    model_config = SettingsConfigDict(
        env_prefix="DISCORD__",
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
    database: DatabaseSettings
    logging: LoggingSettings


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        discord=DiscordSettings(),  # pyright: ignore[reportCallIssue]
        database=DatabaseSettings(),  # pyright: ignore[reportCallIssue]
        logging=LoggingSettings(),
    )
