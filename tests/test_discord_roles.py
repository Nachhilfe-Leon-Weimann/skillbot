from types import SimpleNamespace

from skillbot.core.discord_roles import DiscordRoleResolver
from skillbot.db.models import MemberRole


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

    assert resolver.member_has_role(member, MemberRole.teacher) is True
    assert resolver.member_has_role(member, MemberRole.student) is True
    assert resolver.member_primary_role(member) == MemberRole.teacher


def test_resolver_prefers_configured_id_and_name() -> None:
    settings = SimpleNamespace(
        discord=SimpleNamespace(
            role_ids=SimpleNamespace(student=200),
            role_names=SimpleNamespace(student="schüler"),
        )
    )
    resolver = DiscordRoleResolver(settings)
    guild = _Guild([_Role(200, "x"), _Role(201, "schüler")])

    role = resolver.resolve_guild_role(guild, MemberRole.student)
    assert role is not None
    assert role.id == 200


def test_resolver_matches_ascii_alias_for_umlauts() -> None:
    settings = SimpleNamespace(
        discord=SimpleNamespace(role_names=SimpleNamespace(student="schüler")),
    )
    resolver = DiscordRoleResolver(settings)
    member = _Member([_Role(1, "schueler")])

    assert resolver.member_has_role(member, MemberRole.student) is True
