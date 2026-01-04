import discord
from discord.ext import commands

from .config import Settings


class SkillBot(commands.Bot):
    def __init__(self, settings: Settings):
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents)

        self.settings = settings

    async def setup_hook(self) -> None:
        await self._load_extensions()
        await self._sync_app_commands()

    async def on_ready(self) -> None:
        print(f"Logged in as {self.user}")

    async def _load_extensions(self) -> None:
        extensions = [
            # "skillbot.extensions.admin",
            "skillbot.cogs.teachers"
        ]

        for ext in extensions:
            await self.load_extension(ext)

    async def _sync_app_commands(self) -> None:
        if not self.settings.discord.sync_commands:
            return
        print("[Sync] Start command sync")

        try:
            if self.settings.discord.guild_id:
                print(f"Sync only for guild {self.settings.discord.guild_id}")
                guild = discord.Object(id=self.settings.discord.guild_id)
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                print(f"[Sync] Synced {len(synced)} commands to guild {self.settings.discord.guild_id}")
            else:
                synced = await self.tree.sync()
                print(f"[Sync] Synced {len(synced)} global commands")
        except Exception as e:
            print(f"[Sync] Failed: {e}")
