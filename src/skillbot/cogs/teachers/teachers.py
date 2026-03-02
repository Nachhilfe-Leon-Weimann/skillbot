import logging

import discord
from discord import app_commands
from discord.ext import commands

from skillbot.cogs.teachers.service import TeacherAlreadyEnabled, TeacherEnableError, TeacherEnableService
from skillbot.core.bot import SkillBot
from skillbot.core.permissions import PermissionAction, require_action, require_cmd_env
from skillbot.db.models import CommandEnvKind

log = logging.getLogger(__name__)


class Teachers(commands.GroupCog, name="teachers"):
    """Handling teachers"""

    def __init__(self, bot: SkillBot):
        self.bot = bot
        self.enable_service = TeacherEnableService(bot.db, bot.command_env_service)
        super().__init__()

    @commands.Cog.listener()
    async def on_ready(self):
        log.debug(f"{self.__cog_name__} ready")

    @app_commands.command(name="test")
    @require_action(PermissionAction.TEACHERS_TEST)
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
            result = await self.enable_service.enable_teacher(
                interaction,
                discord_name=discord_name,
                real_name=real_name,
            )
        except TeacherAlreadyEnabled:
            await interaction.response.send_message(
                f"Der Account `{discord_name}` ist bereits als Lehrkraft aktiviert.",
                ephemeral=True,
            )
            return
        except TeacherEnableError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        await interaction.response.send_message(
            (
                f"Lehrkraft `{result.target_discord_name}` wurde aktiviert.\n"
                f"Category: `{result.category_id}`\n"
                f"Cmd-Channel: `{result.cmd_channel_id}`"
            ),
            ephemeral=True,
        )

    @enable.autocomplete("discord_name")
    async def enable_discord_name_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        return await self.enable_service.autocomplete_discord_name(interaction, current)
