import importlib
import logging
import pkgutil

import discord
from discord import app_commands
from discord.ext import commands

from .app_command_logger import AppCommandLogger, AppCommandLogPolicy
from .config import Settings
from .permissions import CommandEnvironmentService, PermissionDenied, PermissionService
from .skillforge import HttpSkillforgeClient, SkillforgeClient, SkillforgeClientNotConfigured

log = logging.getLogger(__name__)


class SkillBot(commands.Bot):
    def __init__(self, settings: Settings):
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents)

        self.settings = settings
        self.skillforge = self._build_skillforge_client(settings)
        self.permission_service = PermissionService(self.skillforge)
        self.command_env_service = CommandEnvironmentService(self.skillforge)

        self.app_cmd_logger = AppCommandLogger(
            policy=AppCommandLogPolicy(
                audit_commands=set(),
                audit_prefixes=("teachers", "students"),
            )
        )

    async def setup_hook(self) -> None:
        await self._load_extensions()
        await self._sync_app_commands()

    async def close(self) -> None:
        await super().close()
        await self.skillforge.close()

    async def on_ready(self) -> None:
        log.info("Logged in as %s", self.user)

    async def on_app_command_completion(self, interaction: discord.Interaction, command) -> None:
        await self.app_cmd_logger.log_success(interaction, command)

    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        await self.app_cmd_logger.log_error(interaction, getattr(interaction, "command", None), error)

        denied_error: PermissionDenied | None = None
        if isinstance(error, PermissionDenied):
            denied_error = error
        elif isinstance(getattr(error, "original", None), PermissionDenied):
            denied_error = error.original  # type: ignore[assignment]

        if denied_error:
            message = str(denied_error)
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
            return

        if isinstance(error, app_commands.CheckFailure):
            message = "Dafür fehlt dir die Berechtigung."
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
            return

    async def _load_extensions(self) -> None:
        """
        Auto-discover subpackages in _skillbot.cogs.*_ and load each package as extension.

        Convention:
        - Each subpackage: _skillbot/cogs/pkg/__init__.py_ provides (async) 'setup(bot)'
        - Skips private packages starting with "_"
        """

        base = "skillbot.cogs"
        cogs_pkg = importlib.import_module(base)

        for m in pkgutil.iter_modules(cogs_pkg.__path__):
            if not m.ispkg:
                continue

            name = m.name
            if name.startswith("_"):
                continue

            ext = f"{base}.{name}"
            await self.load_extension(ext)

    async def _sync_app_commands(self) -> None:
        """
        Synchronize Discord app commands (slash commands).

        Behavior:
        - If syncing is disabled via settings, this method is a no-op.
        - If a guild ID is configured, commands are synced *only* to that guild.
          Otherwise, commands are synced globally.
        """

        if not self.settings.discord.sync_commands:
            log.info("Skip syncing app commands")
            return

        try:
            if self.settings.discord.guild_id:
                log.debug("Sync only for guild %d", self.settings.discord.guild_id)
                guild = discord.Object(id=self.settings.discord.guild_id)
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                log.debug(
                    "Synced commands to guild",
                    extra={"guild_id": self.settings.discord.guild_id, "count": len(synced)},
                )
            else:
                synced = await self.tree.sync()
                log.debug("Synced %d global commands", len(synced))
        except Exception:
            log.exception("Syncing app commands failed (continuing without sync)")

    def _build_skillforge_client(self, settings: Settings) -> SkillforgeClient:
        if settings.skillforge.base_url is None:
            log.warning("SKILLFORGE__BASE_URL is not configured; API-backed commands will fail.")
            return SkillforgeClientNotConfigured()

        token = settings.skillforge.token.get_secret_value() if settings.skillforge.token is not None else None
        return HttpSkillforgeClient(
            base_url=settings.skillforge.base_url,
            token=token,
            timeout_seconds=settings.skillforge.timeout_seconds,
        )
