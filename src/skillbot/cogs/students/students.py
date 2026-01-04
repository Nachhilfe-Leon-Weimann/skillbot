import logging

import discord
from discord import app_commands
from discord.ext import commands

from skillbot.core.bot import SkillBot
from skillbot.core.util.predicates import is_teacher_predicate

log = logging.getLogger(__name__)


class Students(commands.GroupCog, name="students"):
    """Handling students"""

    def __init__(self, bot: SkillBot) -> None:
        self.bot = bot
        super().__init__()

    @commands.Cog.listener()
    async def on_ready(self):
        log.debug(f"{self.__cog_name__} ready")

    @app_commands.command(name="add")
    @app_commands.check(is_teacher_predicate)
    async def add(self, interaction: discord.Interaction, student_name: str, customer_id: int):
        await interaction.response.send_message(f"Okay, {interaction.user.name}!")
