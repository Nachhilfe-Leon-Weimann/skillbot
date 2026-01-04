import logging

import discord
from discord.ext import commands

from .config import Settings

log = logging.getLogger(__name__)


class SkillBot(commands.Bot):
    def __init__(self, settings: Settings):
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents)

        self.settings = settings

    async def setup_hook(self) -> None:
        await self._load_extensions()
        await self._sync_app_commands()

    async def on_ready(self) -> None:
        log.info(f"Logged in as {self.user}")

    async def _load_extensions(self) -> None:
        extensions = [
            "skillbot.cogs.teachers",
        ]

        for ext in extensions:
            await self.load_extension(ext)

    async def _sync_app_commands(self) -> None:
        if not self.settings.discord.sync_commands:
            log.debug("Skip syncing app commands")
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
