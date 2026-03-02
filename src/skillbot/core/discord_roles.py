from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import discord

from skillbot.db.models import MemberRole


@dataclass(frozen=True)
class DiscordRoleResolver:
    settings: object | None = None

    def resolve_guild_role(self, guild: discord.Guild, role: MemberRole) -> discord.Role | None:
        role_id = self._configured_role_id(role)
        if role_id is not None:
            by_id = guild.get_role(role_id)
            if by_id is not None:
                return by_id

        accepted = self._accepted_names(role)
        return next((r for r in guild.roles if r.name.casefold() in accepted), None)

    def member_has_role(self, member: discord.Member, role: MemberRole) -> bool:
        role_id = self._configured_role_id(role)
        if role_id is not None and any(r.id == role_id for r in member.roles):
            return True

        accepted = self._accepted_names(role)
        return any(r.name.casefold() in accepted for r in member.roles)

    def member_primary_role(self, member: discord.Member) -> MemberRole | None:
        for role in (MemberRole.admin, MemberRole.teacher, MemberRole.student):
            if self.member_has_role(member, role):
                return role
        return None

    def _configured_role_id(self, role: MemberRole) -> int | None:
        ids = getattr(getattr(self.settings, "discord", None), "role_ids", None)
        raw = getattr(ids, role.value, None)
        if isinstance(raw, int):
            return raw
        return None

    def _configured_role_name(self, role: MemberRole) -> str | None:
        names = getattr(getattr(self.settings, "discord", None), "role_names", None)
        raw = getattr(names, role.value, None)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
        return None

    def _accepted_names(self, role: MemberRole) -> set[str]:
        values = set(self._default_names(role))
        configured = self._configured_role_name(role)
        if configured:
            values.add(configured)
            ascii_alias = self._to_ascii_alias(configured)
            if ascii_alias:
                values.add(ascii_alias)
        return {v.casefold() for v in values}

    def _default_names(self, role: MemberRole) -> Iterable[str]:
        defaults = {
            MemberRole.admin: ("Admin", "administrator"),
            MemberRole.teacher: ("Lehrer", "teacher"),
            MemberRole.student: ("Schüler", "schueler", "student"),
        }
        return defaults[role]

    def _to_ascii_alias(self, value: str) -> str | None:
        mapped = (
            value.replace("ä", "ae")
            .replace("ö", "oe")
            .replace("ü", "ue")
            .replace("Ä", "Ae")
            .replace("Ö", "Oe")
            .replace("Ü", "Ue")
            .replace("ß", "ss")
        )
        if mapped != value:
            return mapped
        return None
