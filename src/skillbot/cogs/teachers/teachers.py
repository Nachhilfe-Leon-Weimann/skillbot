import logging

import discord
from discord import app_commands
from discord.ext import commands

from skillbot.core.bot import SkillBot

log = logging.getLogger(__name__)


def is_teacher_predicate(interaction: discord.Interaction) -> bool:
    if not interaction.guild:
        return False
    if not isinstance(interaction.user, discord.Member):
        return False

    return any(role.name == "Lehrer" for role in interaction.user.roles)


class Teachers(commands.GroupCog, name="teachers"):
    """Handling teachers"""

    def __init__(self, bot: SkillBot):
        self.bot = bot
        super().__init__()

    @commands.Cog.listener()
    async def on_ready(self):
        log.debug(f"{self.__cog_name__} ready")

    @app_commands.command(name="test")
    @app_commands.check(is_teacher_predicate)
    async def test(self, interaction: discord.Interaction):
        log.info("Called test command")
        await interaction.response.send_message(f"Hey {interaction.user.name}")
