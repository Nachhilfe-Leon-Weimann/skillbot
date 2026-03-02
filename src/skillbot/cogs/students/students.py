import logging

import discord
from discord import app_commands
from discord.ext import commands

from skillbot.cogs.students.service import StudentAlreadyEnabled, StudentEnableError, StudentEnableService
from skillbot.core.bot import SkillBot
from skillbot.core.permissions import PermissionAction, require_action, require_cmd_env
from skillbot.db.models import CommandEnvKind

log = logging.getLogger(__name__)


class Students(commands.GroupCog, name="students"):
    """Handling students"""

    def __init__(self, bot: SkillBot) -> None:
        self.bot = bot
        self.enable_service = StudentEnableService(bot.db)
        super().__init__()

    @commands.Cog.listener()
    async def on_ready(self):
        log.debug(f"{self.__cog_name__} ready")

    @app_commands.command(
        name="enable",
        description="Activates a discord account as student, assigned to yourself.",
    )
    @require_action(PermissionAction.STUDENTS_ENABLE)
    @require_cmd_env(CommandEnvKind.teacher_cmd, owner_bound=True)
    async def enable(
        self,
        interaction: discord.Interaction,
        discord_name: str,
        real_name: str,
        customer_id: int,
    ):
        try:
            result = await self.enable_service.enable_student(
                interaction,
                discord_name=discord_name,
                real_name=real_name,
                customer_id=customer_id,
            )
        except StudentAlreadyEnabled:
            await interaction.response.send_message(
                f"Der Account `{discord_name}` ist bereits aktiviert.",
                ephemeral=True,
            )
            return
        except StudentEnableError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        await interaction.response.send_message(
            (
                f"Schüler `{result.target_discord_name}` wurde aktiviert.\n"
                f"Alias: `{result.alias}`\n"
                f"Party-ID: `{result.party_id}`"
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
