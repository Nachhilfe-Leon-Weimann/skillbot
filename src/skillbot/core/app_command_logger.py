import logging

import discord
from discord import app_commands
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)


class AppCommandLogPolicy(BaseModel):
    """Model for configuring what commands should be logged at what level"""

    audit_commands: set[str] = Field(default_factory=set)
    debug_only_commands: set[str] = Field(default_factory=set)

    audit_prefixes: tuple[str, ...] = ()
    debug_prefixes: tuple[str, ...] = ()

    def is_audit(self, qualified_name: str) -> bool:
        if qualified_name in self.audit_commands:
            return True
        return any(qualified_name.startswith(p) for p in self.audit_prefixes)

    def is_debug_only(self, qualified_name: str) -> bool:
        if qualified_name in self.debug_only_commands:
            return True
        return any(qualified_name.startswith(p) for p in self.debug_prefixes)


class AppCommandLogger:
    """Helper for logging app command excecutions"""

    def __init__(self, *, policy: AppCommandLogPolicy):
        self._policy = policy

    def _qualified_name(self, command: app_commands.Command | app_commands.ContextMenu) -> str:
        return getattr(command, "qualified_name", None) or getattr(command, "name", "unknown")

    def _base_fields(self, interaction: discord.Interaction, command_name: str) -> dict:
        user = interaction.user
        guild = interaction.guild

        return {
            "command": command_name,
            "user_id": getattr(user, "id", None),
            "user": str(user) if user else None,
            "guild_id": guild.id if guild else None,
        }

    async def log_success(self, interaction: discord.Interaction, command) -> None:
        name = self._qualified_name(command)
        fields = self._base_fields(interaction, name)

        if self._policy.is_debug_only(name):
            log.debug("App command ok", extra=fields)
        else:
            log.info("App command ok", extra=fields)

    async def log_error(self, interaction: discord.Interaction, command, error: Exception) -> None:
        name = self._qualified_name(command) if command else "unknown"
        fields = self._base_fields(interaction, name) | {
            "error_type": type(error).__name__,
            "error": str(error),
        }

        is_perm = isinstance(
            error,
            (
                app_commands.MissingPermissions,
                app_commands.MissingRole,
                app_commands.MissingAnyRole,
                app_commands.CheckFailure,
            ),
        )

        if is_perm:
            log.warning("App command denied", extra=fields)
        else:
            log.exception("App command failed", extra=fields)
