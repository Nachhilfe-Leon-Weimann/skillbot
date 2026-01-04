from skillbot.core.bot import SkillBot

from .students import Students


async def setup(bot: SkillBot) -> None:
    await bot.add_cog(Students(bot))
