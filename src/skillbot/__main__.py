import asyncio
import logging

from skillcore.logging import configure_logging, get_logger

from skillbot.core.bot import SkillBot
from skillbot.core.config import get_settings


def _prepare_logging() -> None:
    settings = get_settings()
    configure_logging(settings=settings.logging)

    logging.getLogger("discord").setLevel(logging.WARNING)


async def main() -> None:
    _prepare_logging()
    logger = get_logger(__name__)

    settings = get_settings()
    bot = SkillBot(settings)

    async with bot:
        try:
            await bot.launch()
        except Exception as e:
            logger.exception("Unexpected error during bot launch: %s", e)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\033[1;31m\nCancelled bot execution\n\033[0m")
