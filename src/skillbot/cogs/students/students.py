import logging

import discord
from discord import app_commands
from discord.ext import commands

from skillbot.core.bot import SkillBot
from skillbot.core.permissions import PermissionAction, require_action

log = logging.getLogger(__name__)


class Students(commands.GroupCog, name="students"):
    """Handling students"""

    def __init__(self, bot: SkillBot) -> None:
        self.bot = bot
        super().__init__()

    @commands.Cog.listener()
    async def on_ready(self):
        log.debug(f"{self.__cog_name__} ready")

    @app_commands.command(
        name="enable",
        description="Activates a discord account as student, assigned to yourself.",
    )
    @require_action(PermissionAction.STUDENTS_ENABLE)
    async def enable(self, interaction: discord.Interaction, discord_name: str, customer_id: int):
        await interaction.response.send_message("This feature is not implemented yet.")
