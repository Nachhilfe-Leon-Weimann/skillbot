import logging
from dataclasses import dataclass
from uuid import UUID

import discord
from discord import app_commands
from skillcore.db import Database
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from skillbot.core.discord_roles import DiscordRoleResolver
from skillbot.db.models import MemberRole, StudentProfile, TeacherStudent, User

log = logging.getLogger(__name__)


class StudentEnableError(Exception):
    pass


class StudentAlreadyEnabled(StudentEnableError):
    pass


@dataclass(frozen=True)
class StudentEnableResult:
    target_discord_id: int
    target_discord_name: str
    student_user_id: int
    party_id: UUID
    alias: str


@dataclass(frozen=True)
class _EnableDbState:
    target_discord_id: int
    teacher_user_id: int
    student_user_id: int
    party_id: UUID
    created_user: bool
    created_profile: bool
    created_link: bool
    previous_full_name: str | None


class CustomerResolver:
    async def resolve_party_id(self, session: AsyncSession, customer_id: int) -> UUID:
        customer_uuid = await session.scalar(
            text(
                """
                SELECT customer_id
                FROM ext.sevdesk_contact_map
                WHERE sevdesk_contact_id = :customer_id
                """
            ),
            {"customer_id": customer_id},
        )
        if customer_uuid is None:
            raise StudentEnableError(f"Kunde mit customer_id `{customer_id}` wurde nicht gefunden.")

        rows = (
            await session.execute(
                text(
                    """
                    SELECT cp.party_id, cp.role, cp.is_primary
                    FROM core.customer_party cp
                    WHERE cp.customer_id = :customer_uuid
                    """
                ),
                {"customer_uuid": customer_uuid},
            )
        ).mappings()

        party_id = self._select_party_id(rows)
        if party_id is None:
            raise StudentEnableError(f"Für customer_id `{customer_id}` wurde keine Party-Zuordnung gefunden.")

        party_exists = await session.scalar(
            text(
                """
                SELECT 1
                FROM core.party
                WHERE id = :party_id
                """
            ),
            {"party_id": party_id},
        )
        if party_exists is None:
            raise StudentEnableError("Die zugeordnete Party existiert nicht.")

        return party_id

    def _select_party_id(self, rows) -> UUID | None:
        candidates: list[tuple[int, str, UUID]] = []

        for row in rows:
            party_id = row.get("party_id")
            if party_id is None:
                continue

            role = str(row.get("role") or "")
            is_primary = bool(row.get("is_primary"))
            rank = 2
            if role == "student":
                rank = 0
            elif is_primary:
                rank = 1

            candidates.append((rank, role, party_id))

        if not candidates:
            return None

        candidates.sort(key=lambda x: (x[0], x[1], str(x[2])))
        return candidates[0][2]


class StudentEnableService:
    def __init__(self, db: Database):
        self._db = db
        self._resolver = CustomerResolver()
        self._role_resolver = DiscordRoleResolver()

    async def autocomplete_discord_name(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        guild = interaction.guild
        if guild is None:
            return []

        activated_ids = await self._active_student_discord_ids()
        needle = current.strip().casefold()
        choices: list[app_commands.Choice[str]] = []

        for member in guild.members:
            if member.bot:
                continue
            if member.id in activated_ids:
                continue
            if needle and needle not in member.name.casefold():
                continue

            choices.append(app_commands.Choice(name=f"{member.name} ({member.id})", value=member.name))
            if len(choices) >= 25:
                break

        return choices

    async def enable_student(
        self,
        interaction: discord.Interaction,
        *,
        discord_name: str,
        real_name: str,
        customer_id: int,
    ) -> StudentEnableResult:
        guild = interaction.guild
        if guild is None:
            raise StudentEnableError("Dieser Command kann nur auf einem Server verwendet werden.")
        if not isinstance(interaction.user, discord.Member):
            raise StudentEnableError("Der ausführende Nutzer konnte nicht als Server-Mitglied aufgelöst werden.")

        student_role = self._role_resolver.resolve_guild_role(guild, MemberRole.student)
        if student_role is None:
            raise StudentEnableError("Die Student-Rolle `Schüler` wurde nicht gefunden.")

        target = discord.utils.get(guild.members, name=discord_name)
        if target is None:
            raise StudentEnableError(f"Discord-Account `{discord_name}` wurde nicht gefunden.")
        if target.bot:
            raise StudentEnableError("Bots können nicht als Schüler aktiviert werden.")

        alias = self._student_alias(real_name)
        state = await self._enable_in_db(
            teacher_discord_id=interaction.user.id,
            target=target,
            real_name=real_name,
            customer_id=customer_id,
        )

        role_added = False
        try:
            await target.add_roles(student_role, reason=f"Activated via /students enable by {interaction.user.id}")
            role_added = True
            await target.edit(nick=alias, reason=f"Student alias set by {interaction.user.id}")
        except Exception as exc:
            log.exception("Discord mutation failed during students.enable", exc_info=exc)

            if role_added:
                try:
                    await target.remove_roles(student_role, reason="Rollback after failed students.enable")
                except Exception as rollback_exc:  # pragma: no cover - defensive log path
                    log.exception("Failed to rollback student role after error", exc_info=rollback_exc)

            await self._compensate_db(state)
            raise StudentEnableError("Freischaltung fehlgeschlagen und wurde zurückgerollt.") from exc

        return StudentEnableResult(
            target_discord_id=target.id,
            target_discord_name=target.name,
            student_user_id=state.student_user_id,
            party_id=state.party_id,
            alias=alias,
        )

    async def _active_student_discord_ids(self) -> set[int]:
        async with self._db.session() as session:
            rows = await session.scalars(
                select(User.discord_id).join(StudentProfile, StudentProfile.user_id == User.id)
            )
            return set(rows.all())

    async def _enable_in_db(
        self,
        *,
        teacher_discord_id: int,
        target: discord.Member,
        real_name: str,
        customer_id: int,
    ) -> _EnableDbState:
        async with self._db.session() as session:
            teacher = await session.scalar(
                select(User).where(
                    User.discord_id == teacher_discord_id,
                    User.role == MemberRole.teacher,
                )
            )
            if teacher is None:
                raise StudentEnableError("Nur Lehrkräfte können Schüler freischalten.")

            target_user = await session.scalar(select(User).where(User.discord_id == target.id))
            created_user = False
            previous_full_name: str | None = None

            if target_user is None:
                target_user = User(
                    discord_id=target.id,
                    full_name=real_name.strip(),
                    role=MemberRole.student,
                )
                session.add(target_user)
                await session.flush()
                created_user = True
            else:
                profile = await session.scalar(select(StudentProfile).where(StudentProfile.user_id == target_user.id))
                if profile is not None:
                    raise StudentAlreadyEnabled("Der ausgewählte Account ist bereits aktiviert.")

                if target_user.role != MemberRole.student:
                    raise StudentEnableError("Der ausgewählte Account ist kein Schüler-Account.")

                normalized = real_name.strip()
                if normalized and target_user.full_name != normalized:
                    previous_full_name = target_user.full_name
                    target_user.full_name = normalized

            party_id = await self._resolver.resolve_party_id(session, customer_id)
            party_owner = await session.scalar(select(StudentProfile).where(StudentProfile.party_id == party_id))
            if party_owner is not None:
                raise StudentEnableError("Die angegebene Kundennummer ist bereits einem Schüler zugeordnet.")

            student_profile = StudentProfile(user_id=target_user.id, party_id=party_id)
            session.add(student_profile)
            created_profile = True

            existing_link = await session.scalar(
                select(TeacherStudent).where(TeacherStudent.student_user_id == target_user.id)
            )
            created_link = False
            if existing_link is None:
                session.add(
                    TeacherStudent(
                        teacher_user_id=teacher.id,
                        student_user_id=target_user.id,
                        channel_id=None,
                    )
                )
                created_link = True
            elif existing_link.teacher_user_id != teacher.id:
                raise StudentEnableError("Der Schüler ist bereits einer anderen Lehrkraft zugeordnet.")

            await session.commit()
            return _EnableDbState(
                target_discord_id=target.id,
                teacher_user_id=teacher.id,
                student_user_id=target_user.id,
                party_id=party_id,
                created_user=created_user,
                created_profile=created_profile,
                created_link=created_link,
                previous_full_name=previous_full_name,
            )

    async def _compensate_db(self, state: _EnableDbState) -> None:
        async with self._db.session() as session:
            student_user = await session.scalar(select(User).where(User.id == state.student_user_id))
            if student_user is None:
                return

            if state.created_link:
                link = await session.scalar(
                    select(TeacherStudent).where(
                        TeacherStudent.student_user_id == state.student_user_id,
                        TeacherStudent.teacher_user_id == state.teacher_user_id,
                    )
                )
                if link is not None:
                    await session.delete(link)

            if state.created_profile:
                profile = await session.scalar(
                    select(StudentProfile).where(StudentProfile.user_id == state.student_user_id)
                )
                if profile is not None:
                    await session.delete(profile)

            if state.created_user:
                await session.delete(student_user)
            else:
                if state.previous_full_name is not None:
                    student_user.full_name = state.previous_full_name

            await session.commit()

    def _student_alias(self, real_name: str) -> str:
        normalized = real_name.strip()
        if not normalized:
            raise StudentEnableError("real_name darf nicht leer sein.")

        alias = f"🎒 {normalized}"
        return alias[:32]
