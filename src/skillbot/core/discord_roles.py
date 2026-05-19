import discord

from skillbot.core.models import MemberRole


class DiscordRoleResolver:
    """
    Utility for resolving MemberRoles to actual discord.Roles in a guild,
    and checking if members have the required roles.
    """

    _DEFAULT_NAMES: dict[MemberRole, tuple[str, ...]] = {
        MemberRole.admin: ("Admin",),
        MemberRole.teacher: ("Lehrer",),
        MemberRole.student: ("Schüler",),
    }

    def resolve_guild_role(self, guild: discord.Guild, role: MemberRole) -> discord.Role | None:
        """Resolves a MemberRole to a discord.Role in the given guild."""
        accepted = self._accepted_names(role)
        return next((r for r in guild.roles if r.name.casefold() in accepted), None)

    def member_has_role(self, member: discord.Member, role: MemberRole) -> bool:
        """Checks whether the member has a discord.Role corresponding to the given MemberRole."""
        accepted = self._accepted_names(role)
        return any(r.name.casefold() in accepted for r in member.roles)

    def member_primary_role(self, member: discord.Member) -> MemberRole | None:
        """Returns the highest MemberRole of the member, or None if no matching role is found."""
        for role in (MemberRole.admin, MemberRole.teacher, MemberRole.student):
            if self.member_has_role(member, role):
                return role
        return None

    def _accepted_names(self, role: MemberRole) -> set[str]:
        """Helper to get the set of accepted role names for a given MemberRole, including ASCII aliases."""
        values = set(self._DEFAULT_NAMES[role])
        for name in tuple(values):
            ascii_alias = self._to_ascii_alias(name)
            if ascii_alias:
                values.add(ascii_alias)
        return {v.casefold() for v in values}

    def _to_ascii_alias(self, value: str) -> str | None:
        mapped = (
            value
            .replace("ä", "ae")
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
