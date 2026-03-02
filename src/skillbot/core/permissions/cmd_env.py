from dataclasses import dataclass

import discord
from skillcore.db import Database
from sqlalchemy import select

from skillbot.core.discord_roles import DiscordRoleResolver
from skillbot.db.models import CommandEnvChannel, CommandEnvKind, MemberRole, User


@dataclass(frozen=True)
class CmdEnvDecision:
    allowed: bool
    kind: str
    reason: str
    channel_id: int | None = None
    owner_user_id: int | None = None


class CommandEnvironmentService:
    def __init__(self, db: Database):
        self._db = db
        self._role_resolver = DiscordRoleResolver()

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

        kind_value = kind_enum.value
        channel_id = getattr(channel, "id", None)
        if channel_id is None:
            return CmdEnvDecision(False, kind_value, "Channel id missing.")

        env = await self.get_active_channel(guild.id, channel_id, kind_enum)
        if env is None:
            return CmdEnvDecision(
                False,
                kind_value,
                "Channel is not whitelisted for this command environment.",
                channel_id=channel_id,
            )

        if not owner_bound:
            return CmdEnvDecision(
                True,
                kind_value,
                "Channel is whitelisted.",
                channel_id=channel_id,
                owner_user_id=env.owner_user_id,
            )

        user = interaction.user
        if isinstance(user, discord.Member) and self._role_resolver.member_has_role(user, MemberRole.admin):
            return CmdEnvDecision(
                True,
                kind_value,
                "Admin bypass for owner-bound command environment.",
                channel_id=channel_id,
                owner_user_id=env.owner_user_id,
            )

        if env.owner_user_id is None:
            return CmdEnvDecision(
                False,
                kind_value,
                "Owner-bound command environment has no owner.",
                channel_id=channel_id,
                owner_user_id=None,
            )

        actor_discord_id = getattr(user, "id", None)
        if actor_discord_id is None:
            return CmdEnvDecision(
                False,
                kind_value,
                "Actor id missing.",
                channel_id=channel_id,
                owner_user_id=env.owner_user_id,
            )

        actor_user_id = await self._skillbot_user_id(actor_discord_id)
        if actor_user_id is None or actor_user_id != env.owner_user_id:
            return CmdEnvDecision(
                False,
                kind_value,
                "Channel belongs to a different owner.",
                channel_id=channel_id,
                owner_user_id=env.owner_user_id,
            )

        return CmdEnvDecision(
            True,
            kind_value,
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

        async with self._db.session() as session:
            env = await session.scalar(
                select(CommandEnvChannel).where(
                    CommandEnvChannel.guild_id == guild_id,
                    CommandEnvChannel.channel_id == channel_id,
                    CommandEnvChannel.kind == kind_enum,
                    CommandEnvChannel.active.is_(True),
                )
            )
            return env

    async def get_owner_channel_id(
        self,
        *,
        guild_id: int,
        owner_user_id: int,
        kind: CommandEnvKind,
    ) -> int | None:
        async with self._db.session() as session:
            row = await session.scalar(
                select(CommandEnvChannel.channel_id).where(
                    CommandEnvChannel.guild_id == guild_id,
                    CommandEnvChannel.owner_user_id == owner_user_id,
                    CommandEnvChannel.kind == kind,
                    CommandEnvChannel.active.is_(True),
                )
            )
            return row

    async def upsert_channel(
        self,
        *,
        guild_id: int,
        channel_id: int,
        kind: CommandEnvKind,
        owner_user_id: int | None,
    ) -> None:
        async with self._db.session() as session:
            existing = await session.scalar(select(CommandEnvChannel).where(CommandEnvChannel.channel_id == channel_id))
            if existing is None:
                session.add(
                    CommandEnvChannel(
                        guild_id=guild_id,
                        channel_id=channel_id,
                        kind=kind,
                        owner_user_id=owner_user_id,
                        active=True,
                    )
                )
            else:
                existing.guild_id = guild_id
                existing.kind = kind
                existing.owner_user_id = owner_user_id
                existing.active = True

            await session.commit()

    async def _skillbot_user_id(self, discord_id: int) -> int | None:
        async with self._db.session() as session:
            return await session.scalar(select(User.id).where(User.discord_id == discord_id))

    def _parse_kind(self, kind: CommandEnvKind | str) -> CommandEnvKind | None:
        if isinstance(kind, CommandEnvKind):
            return kind
        try:
            return CommandEnvKind(str(kind))
        except ValueError:
            return None
