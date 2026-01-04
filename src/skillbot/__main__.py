import asyncio
import logging

import discord
from skillcore.logging import configure_logging

from skillbot.core.bot import SkillBot
from skillbot.core.config import get_settings


def _prepare_logging() -> None:
    settings = get_settings()
    configure_logging(level=settings.logging.level_int())

    logging.getLogger("discord").setLevel(logging.WARNING)


async def main() -> None:
    _prepare_logging()

    settings = get_settings()
    bot = SkillBot(settings)

    async with bot:
        try:
            await bot.start(settings.discord.token)
        except discord.LoginFailure:
            print("Invalid token (DISCORD_TOKEN)")
        except discord.HTTPException as e:
            print(f"Discord HTTP error: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")


if __name__ == "__main__":
    print("Start bot execution")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Cancelled bot execution")
