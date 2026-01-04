from skillbot.core.bot import SkillBot

from .teachers import Teachers


async def setup(bot: SkillBot) -> None:
    await bot.add_cog(Teachers(bot))
