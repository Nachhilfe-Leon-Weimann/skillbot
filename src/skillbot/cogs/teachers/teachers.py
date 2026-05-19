import logging

import discord
from discord import app_commands
from discord.ext import commands

from skillbot.cogs.teachers.service import TeacherEnableError, TeacherEnableService
from skillbot.core.bot import SkillBot
from skillbot.core.models import CommandEnvKind
from skillbot.core.permissions import PermissionAction, require_action, require_cmd_env

log = logging.getLogger(__name__)


class Teachers(commands.GroupCog, name="teachers"):
    """Handling teachers"""

    def __init__(self, bot: SkillBot):
        self.bot = bot
        self.service = TeacherEnableService(bot.skillforge, bot.command_env_service)
        super().__init__()

    @commands.Cog.listener()
    async def on_ready(self):
        log.debug(f"{self.__cog_name__} ready")

    @app_commands.command(name="test")
    async def test(self, interaction: discord.Interaction):
        log.info("Called teachers.test command")
        await interaction.response.send_message(f"Hey {interaction.user.name}")

    @app_commands.command(name="enable", description="Activates a Discord account as teacher.")
    @require_action(PermissionAction.TEACHERS_ENABLE)
    @require_cmd_env(CommandEnvKind.admin_cmd)
    async def enable(
        self,
        interaction: discord.Interaction,
        discord_name: str,
        real_name: str,
    ):
        try:
            result = await self.service.enable_teacher(
                interaction,
                discord_name=discord_name,
                real_name=real_name,
            )
        except TeacherEnableError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        await interaction.response.send_message(
            f"`{result.target_discord_name}` wurde als Lehrer aktiviert.",
            ephemeral=True,
        )

    @enable.autocomplete("discord_name")
    async def enable_discord_name_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        return await self.service.autocomplete_discord_name(interaction, current)
