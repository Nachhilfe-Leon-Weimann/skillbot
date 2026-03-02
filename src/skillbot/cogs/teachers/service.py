import logging
from dataclasses import dataclass

import discord
from discord import app_commands
from skillcore.db import Database
from sqlalchemy import select

from skillbot.core.discord_roles import DiscordRoleResolver
from skillbot.core.permissions import CommandEnvironmentService
from skillbot.db.models import CommandEnvKind, MemberRole, StudentProfile, TeacherProfile, User

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


@dataclass(frozen=True)
class _UserState:
    user_id: int
    created_user: bool
    previous_role: MemberRole | None
    previous_full_name: str | None
    existing_category_id: int | None


class TeacherEnableService:
    def __init__(
        self,
        db: Database,
        command_env_service: CommandEnvironmentService,
    ):
        self._db = db
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

        cmd_decision = await self._command_env_service.authorize(
            interaction,
            kind=CommandEnvKind.admin_cmd,
            owner_bound=False,
        )
        if not cmd_decision.allowed:
            raise TeacherEnableError(str(cmd_decision.reason))

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

        user_state = await self._upsert_teacher_user(target.id, real_name)
        if user_state.existing_category_id is not None:
            category = guild.get_channel(user_state.existing_category_id)  # type: ignore
            if isinstance(category, discord.CategoryChannel):
                cmd_channel_id = await self._command_env_service.get_owner_channel_id(
                    guild_id=guild.id,
                    owner_user_id=user_state.user_id,
                    kind=CommandEnvKind.teacher_cmd,
                )
                if cmd_channel_id is not None and isinstance(guild.get_channel(cmd_channel_id), discord.TextChannel):
                    role_added = False
                    nick_changed = False
                    try:
                        await target.add_roles(
                            teacher_role,
                            reason=f"Activated via /teachers enable by {interaction.user.id}",
                        )
                        role_added = not had_teacher_role
                        await target.edit(
                            nick=alias,
                            reason=f"Teacher alias set by {interaction.user.id}",
                        )
                        nick_changed = previous_nick != alias
                    except Exception as exc:
                        log.exception("teachers.enable failed in reuse path", exc_info=exc)
                        if role_added:
                            try:
                                await target.remove_roles(teacher_role, reason="Rollback after failed teachers.enable")
                            except Exception as rollback_exc:  # pragma: no cover
                                log.exception("Rollback failed for teacher role", exc_info=rollback_exc)
                        if nick_changed:
                            try:
                                await target.edit(nick=previous_nick, reason="Rollback after failed teachers.enable")
                            except Exception as rollback_exc:  # pragma: no cover
                                log.exception("Rollback failed for teacher nickname", exc_info=rollback_exc)
                        await self._rollback_user(user_state)
                        raise TeacherEnableError("Lehrer-Aktivierung fehlgeschlagen und wurde zurückgerollt.") from exc
                    return TeacherEnableResult(
                        target_discord_id=target.id,
                        target_discord_name=target.name,
                        teacher_user_id=user_state.user_id,
                        category_id=category.id,
                        cmd_channel_id=cmd_channel_id,
                    )

        category_created = False
        channel_created = False
        role_added = False
        nick_changed = False
        category: discord.CategoryChannel | None = None
        cmd_channel: discord.TextChannel | None = None

        try:
            await target.add_roles(teacher_role, reason=f"Activated via /teachers enable by {interaction.user.id}")
            role_added = not had_teacher_role
            await target.edit(
                nick=alias,
                reason=f"Teacher alias set by {interaction.user.id}",
            )
            nick_changed = previous_nick != alias

            category, category_created = await self._ensure_teacher_category(guild, target, real_name)
            cmd_channel, channel_created = await self._ensure_teacher_cmd_channel(category)

            await self._persist_teacher_profile(
                user_id=user_state.user_id,
                category_id=category.id,
            )
            await self._command_env_service.upsert_channel(
                guild_id=guild.id,
                channel_id=cmd_channel.id,
                kind=CommandEnvKind.teacher_cmd,
                owner_user_id=user_state.user_id,
            )
        except TeacherAlreadyEnabled:
            raise
        except Exception as exc:
            log.exception("teachers.enable failed", exc_info=exc)
            await self._compensate(
                user_state=user_state,
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
            teacher_user_id=user_state.user_id,
            category_id=category.id,
            cmd_channel_id=cmd_channel.id,
        )

    async def _teacher_and_student_discord_ids(self) -> tuple[set[int], set[int]]:
        async with self._db.session() as session:
            teacher_rows = await session.scalars(
                select(User.discord_id).join(TeacherProfile, TeacherProfile.user_id == User.id)
            )
            teachers = set(teacher_rows.all())

            student_rows = await session.scalars(select(User.discord_id).where(User.role == MemberRole.student))
            students = set(student_rows.all())

            profile_rows = await session.scalars(
                select(User.discord_id).join(StudentProfile, StudentProfile.user_id == User.id)
            )
            students.update(profile_rows.all())

            return teachers, students

    async def _upsert_teacher_user(self, discord_id: int, real_name: str) -> _UserState:
        normalized_name = real_name.strip()
        if not normalized_name:
            raise TeacherEnableError("real_name darf nicht leer sein.")

        async with self._db.session() as session:
            user = await session.scalar(select(User).where(User.discord_id == discord_id))
            created_user = False
            previous_role: MemberRole | None = None
            previous_full_name: str | None = None

            if user is None:
                user = User(
                    discord_id=discord_id,
                    full_name=normalized_name,
                    role=MemberRole.teacher,
                )
                session.add(user)
                await session.flush()
                created_user = True
            else:
                student_profile = await session.scalar(select(StudentProfile).where(StudentProfile.user_id == user.id))
                if student_profile is not None or user.role == MemberRole.student:
                    raise TeacherEnableError("Schüler können nicht als Lehrkräfte aktiviert werden.")

                if user.role != MemberRole.teacher:
                    previous_role = user.role
                    user.role = MemberRole.teacher

                if user.full_name != normalized_name:
                    previous_full_name = user.full_name
                    user.full_name = normalized_name

            teacher_profile = await session.scalar(select(TeacherProfile).where(TeacherProfile.user_id == user.id))
            existing_category_id = teacher_profile.teaching_category_id if teacher_profile else None

            await session.commit()
            return _UserState(
                user_id=user.id,
                created_user=created_user,
                previous_role=previous_role,
                previous_full_name=previous_full_name,
                existing_category_id=existing_category_id,
            )

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
            overwrites=overwrites,  # type: ignore
            reason=f"Teacher category for {real_name}",
        )
        return category, True

    async def _ensure_teacher_cmd_channel(self, category: discord.CategoryChannel) -> tuple[discord.TextChannel, bool]:
        existing = discord.utils.get(category.text_channels, name="cmd")
        if isinstance(existing, discord.TextChannel):
            return existing, False

        channel = await category.create_text_channel("cmd", reason="Teacher command channel")
        return channel, True

    async def _persist_teacher_profile(self, *, user_id: int, category_id: int) -> None:
        async with self._db.session() as session:
            profile = await session.scalar(select(TeacherProfile).where(TeacherProfile.user_id == user_id))
            if profile is None:
                session.add(
                    TeacherProfile(
                        user_id=user_id,
                        teaching_category_id=category_id,
                    )
                )
            else:
                profile.teaching_category_id = category_id

            await session.commit()

    async def _compensate(
        self,
        *,
        user_state: _UserState,
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

        await self._rollback_user(user_state)

    async def _rollback_user(self, state: _UserState) -> None:
        async with self._db.session() as session:
            user = await session.scalar(select(User).where(User.id == state.user_id))
            if user is None:
                return

            if state.created_user:
                await session.delete(user)
            else:
                if state.previous_role is not None:
                    user.role = state.previous_role
                if state.previous_full_name is not None:
                    user.full_name = state.previous_full_name

            await session.commit()

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
