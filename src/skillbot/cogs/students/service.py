import logging
from dataclasses import dataclass
from uuid import UUID

import discord
from discord import app_commands

from skillbot.core.discord_roles import DiscordRoleResolver
from skillbot.core.models import ActivateStudentRequest, MemberRole
from skillbot.core.skillforge import SkillforgeClient, SkillforgeClientNotConfigured

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


class CustomerResolver:
    """Local helper for the legacy customer-party selection rule.

    Skillforge should own the actual customer lookup. The bot only keeps the
    deterministic selection rule here because it is useful and already tested.
    """

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
    def __init__(self, client: SkillforgeClient | None = None):
        self._client = client if client is not None else SkillforgeClientNotConfigured()
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
            raise StudentEnableError("Die Schüler-Rolle `Schüler` wurde nicht gefunden.")

        target = discord.utils.get(guild.members, name=discord_name)
        if target is None:
            raise StudentEnableError(f"Discord-Account `{discord_name}` wurde nicht gefunden.")
        if target.bot:
            raise StudentEnableError("Bots können nicht als Schüler aktiviert werden.")

        alias = self._student_alias(real_name)
        previous_nick = target.nick
        had_student_role = self._role_resolver.member_has_role(target, MemberRole.student)
        role_added = False
        nick_changed = False

        try:
            await target.add_roles(student_role, reason=f"Activated via /students enable by {interaction.user.id}")
            role_added = not had_student_role
            await target.edit(nick=alias, reason=f"Student alias set by {interaction.user.id}")
            nick_changed = previous_nick != alias

            student = await self._client.activate_student(
                ActivateStudentRequest(
                    teacher_discord_id=interaction.user.id,
                    student_discord_id=target.id,
                    full_name=real_name.strip(),
                    customer_id=customer_id,
                )
            )
        except Exception as exc:
            log.exception("students.enable failed", exc_info=exc)
            if role_added:
                try:
                    await target.remove_roles(student_role, reason="Rollback after failed students.enable")
                except Exception as rollback_exc:  # pragma: no cover
                    log.exception("Rollback failed for student role", exc_info=rollback_exc)
            if nick_changed:
                try:
                    await target.edit(nick=previous_nick, reason="Rollback after failed students.enable")
                except Exception as rollback_exc:  # pragma: no cover
                    log.exception("Rollback failed for student nickname", exc_info=rollback_exc)
            raise StudentEnableError("Freischaltung fehlgeschlagen und wurde zurückgerollt.") from exc

        return StudentEnableResult(
            target_discord_id=target.id,
            target_discord_name=target.name,
            student_user_id=student.user_id,
            party_id=student.party_id,
            alias=alias,
        )

    async def _active_student_discord_ids(self) -> set[int]:
        return await self._client.list_student_discord_ids()

    def _student_alias(self, real_name: str) -> str:
        normalized = real_name.strip()
        if not normalized:
            raise StudentEnableError("real_name darf nicht leer sein.")

        alias = f"🎒 {normalized}"
        return alias[:32]
