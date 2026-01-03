import asyncio

import discord

from skillbot.bot import SkillBot
from skillbot.config import get_settings


async def main() -> None:
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
