import logging
from dataclasses import dataclass

import discord
from discord import app_commands

from skillbot.core.discord_roles import DiscordRoleResolver
from skillbot.core.models import ActivateTeacherRequest, CommandEnvKind, MemberRole
from skillbot.core.permissions import CommandEnvironmentService
from skillbot.core.skillforge import SkillforgeClient, SkillforgeClientNotConfigured

log = logging.getLogger(__name__)


class TeacherEnableError(Exception):
    pass


class TeacherAlreadyEnabled(TeacherEnableError):
    pass


@dataclass(frozen=True)
class TeacherEnableResult:
    target_discord_id: int
    target_discord_name: str
    teacher_user_id: int
    category_id: int
    cmd_channel_id: int


class TeacherEnableService:
    def __init__(
        self,
        client: SkillforgeClient | None = None,
        command_env_service: CommandEnvironmentService | None = None,
    ):
        self._client = client if client is not None else SkillforgeClientNotConfigured()
        self._role_resolver = DiscordRoleResolver()
        self._command_env_service = command_env_service

    async def autocomplete_discord_name(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        guild = interaction.guild
        if guild is None:
            return []

        teacher_ids, student_ids = await self._teacher_and_student_discord_ids()
        needle = current.strip().casefold()
        choices: list[app_commands.Choice[str]] = []

        for member in guild.members:
            if member.bot:
                continue
            if member.id in teacher_ids:
                continue
            if member.id in student_ids:
                continue
            if self._role_resolver.member_has_role(member, MemberRole.student):
                continue
            if needle and needle not in member.name.casefold():
                continue

            choices.append(app_commands.Choice(name=f"{member.name} ({member.id})", value=member.name))
            if len(choices) >= 25:
                break

        return choices

    async def enable_teacher(
        self,
        interaction: discord.Interaction,
        *,
        discord_name: str,
        real_name: str,
    ) -> TeacherEnableResult:
        guild = interaction.guild
        if guild is None:
            raise TeacherEnableError("Dieser Command kann nur auf einem Server verwendet werden.")
        if not isinstance(interaction.user, discord.Member):
            raise TeacherEnableError("Actor konnte nicht als Server-Mitglied aufgelöst werden.")
        if not self._role_resolver.member_has_role(interaction.user, MemberRole.admin):
            raise TeacherEnableError("Nur Admins dürfen Lehrkräfte aktivieren.")

        if self._command_env_service is not None:
            decision = await self._command_env_service.authorize(
                interaction,
                kind=CommandEnvKind.admin_cmd,
                owner_bound=False,
            )
            if not decision.allowed:
                raise TeacherEnableError(str(decision.reason))

        teacher_role = self._role_resolver.resolve_guild_role(guild, MemberRole.teacher)
        if teacher_role is None:
            raise TeacherEnableError("Lehrer-Rolle `Lehrer` wurde nicht gefunden.")

        target = discord.utils.get(guild.members, name=discord_name)
        if target is None:
            raise TeacherEnableError(f"Discord-Account `{discord_name}` wurde nicht gefunden.")
        if target.bot:
            raise TeacherEnableError("Bots können nicht als Lehrkräfte aktiviert werden.")
        if self._role_resolver.member_has_role(target, MemberRole.student):
            raise TeacherEnableError("Schüler können nicht als Lehrkräfte aktiviert werden.")

        alias = self._teacher_alias(real_name)
        previous_nick = target.nick
        had_teacher_role = self._role_resolver.member_has_role(target, MemberRole.teacher)
        category_created = False
        channel_created = False
        role_added = False
        nick_changed = False
        category: discord.CategoryChannel | None = None
        cmd_channel: discord.TextChannel | None = None

        try:
            await target.add_roles(teacher_role, reason=f"Activated via /teachers enable by {interaction.user.id}")
            role_added = not had_teacher_role
            await target.edit(nick=alias, reason=f"Teacher alias set by {interaction.user.id}")
            nick_changed = previous_nick != alias

            category, category_created = await self._ensure_teacher_category(guild, target, real_name)
            cmd_channel, channel_created = await self._ensure_teacher_cmd_channel(category)

            teacher = await self._client.activate_teacher(
                ActivateTeacherRequest(
                    discord_id=target.id,
                    full_name=real_name.strip(),
                    teaching_category_id=category.id,
                    command_channel_id=cmd_channel.id,
                )
            )
        except Exception as exc:
            log.exception("teachers.enable failed", exc_info=exc)
            await self._compensate(
                target=target,
                teacher_role=teacher_role,
                role_added=role_added,
                previous_nick=previous_nick,
                nick_changed=nick_changed,
                category=category,
                category_created=category_created,
                cmd_channel=cmd_channel,
                channel_created=channel_created,
            )
            raise TeacherEnableError("Lehrer-Aktivierung fehlgeschlagen und wurde zurückgerollt.") from exc

        return TeacherEnableResult(
            target_discord_id=target.id,
            target_discord_name=target.name,
            teacher_user_id=teacher.user_id,
            category_id=category.id,
            cmd_channel_id=cmd_channel.id,
        )

    async def _teacher_and_student_discord_ids(self) -> tuple[set[int], set[int]]:
        teacher_ids = await self._client.list_teacher_discord_ids()
        student_ids = await self._client.list_student_discord_ids()
        return teacher_ids, student_ids

    async def _ensure_teacher_category(
        self,
        guild: discord.Guild,
        target: discord.Member,
        real_name: str,
    ) -> tuple[discord.CategoryChannel, bool]:
        category_name = self._teacher_alias(real_name)

        existing = discord.utils.get(guild.categories, name=category_name)
        if isinstance(existing, discord.CategoryChannel):
            return existing, False

        overwrites = self._category_overwrites(guild, target)
        category = await guild.create_category(
            name=category_name,
            overwrites=overwrites,  # type: ignore[arg-type]
            reason=f"Teacher category for {real_name}",
        )
        return category, True

    async def _ensure_teacher_cmd_channel(self, category: discord.CategoryChannel) -> tuple[discord.TextChannel, bool]:
        existing = discord.utils.get(category.text_channels, name="cmd")
        if isinstance(existing, discord.TextChannel):
            return existing, False

        channel = await category.create_text_channel("cmd", reason="Teacher command channel")
        return channel, True

    async def _compensate(
        self,
        *,
        target: discord.Member,
        teacher_role: discord.Role,
        role_added: bool,
        previous_nick: str | None,
        nick_changed: bool,
        category: discord.CategoryChannel | None,
        category_created: bool,
        cmd_channel: discord.TextChannel | None,
        channel_created: bool,
    ) -> None:
        if role_added:
            try:
                await target.remove_roles(teacher_role, reason="Rollback after failed teachers.enable")
            except Exception as exc:  # pragma: no cover
                log.exception("Rollback failed for teacher role", exc_info=exc)

        if nick_changed:
            try:
                await target.edit(nick=previous_nick, reason="Rollback after failed teachers.enable")
            except Exception as exc:  # pragma: no cover
                log.exception("Rollback failed for teacher nickname", exc_info=exc)

        if channel_created and cmd_channel is not None:
            try:
                await cmd_channel.delete(reason="Rollback after failed teachers.enable")
            except Exception as exc:  # pragma: no cover
                log.exception("Rollback failed for teacher command channel", exc_info=exc)

        if category_created and category is not None:
            try:
                await category.delete(reason="Rollback after failed teachers.enable")
            except Exception as exc:  # pragma: no cover
                log.exception("Rollback failed for teacher category", exc_info=exc)

    def _category_overwrites(
        self,
        guild: discord.Guild,
        target: discord.Member,
    ) -> dict[discord.abc.Snowflake, discord.PermissionOverwrite]:
        overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            target: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        }

        admin_role = self._role_resolver.resolve_guild_role(guild, MemberRole.admin)
        if admin_role is not None:
            overwrites[admin_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True,
                read_message_history=True,
            )

        if guild.me is not None:
            overwrites[guild.me] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True,
                read_message_history=True,
                manage_messages=True,
            )

        return overwrites

    def _teacher_alias(self, real_name: str) -> str:
        normalized = real_name.strip()
        if not normalized:
            raise TeacherEnableError("real_name darf nicht leer sein.")

        alias = f"🎓 {normalized}"
        return alias[:32]
