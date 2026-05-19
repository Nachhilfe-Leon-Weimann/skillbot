from dataclasses import dataclass

import discord

from skillbot.core.discord_roles import DiscordRoleResolver
from skillbot.core.models import CommandEnvChannel, CommandEnvKind, MemberRole
from skillbot.core.skillforge import SkillforgeClient, SkillforgeClientNotConfigured


@dataclass(frozen=True)
class CmdEnvDecision:
    allowed: bool
    kind: str
    reason: str
    channel_id: int | None = None
    owner_user_id: int | None = None


class CommandEnvironmentService:
    def __init__(
        self,
        client: SkillforgeClient | None = None,
        *,
        db: object | None = None,
        role_resolver: DiscordRoleResolver | None = None,
    ) -> None:
        del db  # compatibility only; command environments no longer use the DB directly.
        self._client = client or SkillforgeClientNotConfigured()
        self._role_resolver = role_resolver or DiscordRoleResolver()

    async def authorize(
        self,
        interaction: discord.Interaction,
        *,
        kind: CommandEnvKind | str,
        owner_bound: bool = False,
    ) -> CmdEnvDecision:
        kind_enum = self._parse_kind(kind)
        if kind_enum is None:
            return CmdEnvDecision(False, str(kind), "Unknown command environment kind.")

        guild = interaction.guild
        channel = interaction.channel
        if guild is None or channel is None:
            return CmdEnvDecision(False, kind_enum.value, "Command environments require guild channels.")

        channel_id = getattr(channel, "id", None)
        if channel_id is None:
            return CmdEnvDecision(False, kind_enum.value, "Channel id missing.")

        env = await self.get_active_channel(guild.id, channel_id, kind_enum)
        if env is None:
            return CmdEnvDecision(
                False,
                kind_enum.value,
                "Channel is not whitelisted for this command environment.",
                channel_id=channel_id,
            )

        if not owner_bound:
            return CmdEnvDecision(
                True,
                kind_enum.value,
                "Channel is whitelisted.",
                channel_id=channel_id,
                owner_user_id=env.owner_user_id,
            )

        user = interaction.user
        if isinstance(user, discord.Member) and self._role_resolver.member_has_role(user, MemberRole.admin):
            return CmdEnvDecision(
                True,
                kind_enum.value,
                "Admin bypass for owner-bound command environment.",
                channel_id=channel_id,
                owner_user_id=env.owner_user_id,
            )

        if env.owner_user_id is None:
            return CmdEnvDecision(
                False,
                kind_enum.value,
                "Owner-bound command environment has no owner.",
                channel_id=channel_id,
                owner_user_id=None,
            )

        actor_discord_id = getattr(user, "id", None)
        if actor_discord_id is None:
            return CmdEnvDecision(
                False,
                kind_enum.value,
                "Actor id missing.",
                channel_id=channel_id,
                owner_user_id=env.owner_user_id,
            )

        actor_user_id = await self._client.get_user_id_by_discord_id(actor_discord_id)
        if actor_user_id is None or actor_user_id != env.owner_user_id:
            return CmdEnvDecision(
                False,
                kind_enum.value,
                "Channel belongs to a different owner.",
                channel_id=channel_id,
                owner_user_id=env.owner_user_id,
            )

        return CmdEnvDecision(
            True,
            kind_enum.value,
            "Owner-bound channel matches actor.",
            channel_id=channel_id,
            owner_user_id=env.owner_user_id,
        )

    async def get_active_channel(
        self,
        guild_id: int,
        channel_id: int,
        kind: CommandEnvKind | str,
    ) -> CommandEnvChannel | None:
        kind_enum = self._parse_kind(kind)
        if kind_enum is None:
            return None
        return await self._client.get_command_env_channel(guild_id=guild_id, channel_id=channel_id, kind=kind_enum)

    async def get_owner_channel_id(
        self,
        *,
        guild_id: int,
        owner_user_id: int,
        kind: CommandEnvKind,
    ) -> int | None:
        return await self._client.get_owner_command_env_channel_id(
            guild_id=guild_id,
            owner_user_id=owner_user_id,
            kind=kind,
        )

    async def upsert_channel(
        self,
        *,
        guild_id: int,
        channel_id: int,
        kind: CommandEnvKind,
        owner_user_id: int | None,
    ) -> None:
        await self._client.upsert_command_env_channel(
            guild_id=guild_id,
            channel_id=channel_id,
            kind=kind,
            owner_user_id=owner_user_id,
        )

    def _parse_kind(self, kind: CommandEnvKind | str) -> CommandEnvKind | None:
        if isinstance(kind, CommandEnvKind):
            return kind
        try:
            return CommandEnvKind(str(kind))
        except ValueError:
            return None

