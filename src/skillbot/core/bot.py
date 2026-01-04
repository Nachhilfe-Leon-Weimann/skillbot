import importlib
import logging
import pkgutil

import discord
from discord import app_commands
from discord.ext import commands

from .app_command_logger import AppCommandLogger, AppCommandLogPolicy
from .config import Settings

log = logging.getLogger(__name__)


class SkillBot(commands.Bot):
    def __init__(self, settings: Settings):
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents)

        self.settings = settings

        self.app_cmd_logger = AppCommandLogger(
            policy=AppCommandLogPolicy(
                audit_commands=set(),
                audit_prefixes=("teachers", "students"),
            )
        )

    async def setup_hook(self) -> None:
        await self._load_extensions()
        await self._sync_app_commands()

    async def on_ready(self) -> None:
        log.info("Logged in as %s", self.user)

    async def on_app_command_completion(self, interaction: discord.Interaction, command) -> None:
        await self.app_cmd_logger.log_success(interaction, command)

    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        await self.app_cmd_logger.log_error(interaction, getattr(interaction, "command", None), error)

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
