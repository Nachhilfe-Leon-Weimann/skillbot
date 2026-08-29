import asyncio

from skillforge_client.models import MemberRole

from skillbot.core.config import get_settings
from skillbot.core.skillforge import SkillForgeClient
from skillbot.core.skillforge.client import DiscordUserUpsertRequest
from skillbot.core.skillforge.errors import SkillForgeError


async def main():
    client = SkillForgeClient(get_settings().skillforge)
    print(await client.liveness_check())

    await client.upsert_discord_user(
        681190457719521430, DiscordUserUpsertRequest(nick_name="Leon Weimann", role=MemberRole.ADMIN)
    )


try:
    asyncio.run(main())
except SkillForgeError as e:
    print("SkillForgeError: ", e)
