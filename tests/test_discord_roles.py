from skillbot.core.discord_roles import DiscordRoleResolver
from skillbot.core.models import MemberRole


class _Role:
    def __init__(self, role_id: int, name: str):
        self.id = role_id
        self.name = name


class _Member:
    def __init__(self, roles):
        self.roles = roles


class _Guild:
    def __init__(self, roles):
        self.roles = roles

    def get_role(self, role_id: int):
        return next((r for r in self.roles if r.id == role_id), None)


def test_resolver_uses_default_german_names() -> None:
    resolver = DiscordRoleResolver()
    member = _Member([_Role(1, "Lehrer"), _Role(2, "Schüler")])

    assert resolver.member_has_role(member, MemberRole.teacher) is True  # pyright: ignore[reportArgumentType]
    assert resolver.member_has_role(member, MemberRole.student) is True  # pyright: ignore[reportArgumentType]
    assert resolver.member_primary_role(member) == MemberRole.teacher  # pyright: ignore[reportArgumentType]


def test_resolver_finds_role_by_case_insensitive_name() -> None:
    resolver = DiscordRoleResolver()
    guild = _Guild([_Role(200, "x"), _Role(201, "schüler")])

    role = resolver.resolve_guild_role(guild, MemberRole.student)  # pyright: ignore[reportArgumentType]
    assert role is not None
    assert role.id == 201


def test_resolver_matches_ascii_alias_for_umlauts() -> None:
    resolver = DiscordRoleResolver()
    member = _Member([_Role(1, "schueler")])

    assert resolver.member_has_role(member, MemberRole.student) is True  # pyright: ignore[reportArgumentType]
