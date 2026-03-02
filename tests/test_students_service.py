import asyncio
from uuid import UUID, uuid4

import pytest
from skillcore.db import Database

from skillbot.cogs.students.service import CustomerResolver, StudentEnableError, StudentEnableService


class _MemberStub:
    def __init__(self, member_id: int, name: str, *, bot: bool = False):
        self.id = member_id
        self.name = name
        self.bot = bot


class _GuildStub:
    def __init__(self, members):
        self.members = members


class _InteractionStub:
    def __init__(self, guild):
        self.guild = guild


def _service() -> StudentEnableService:
    db = Database.__new__(Database)  # lightweight placeholder; tests only call pure helper logic
    return StudentEnableService(db)


def test_customer_resolver_prefers_student_role_party() -> None:
    resolver = CustomerResolver()
    student_party = uuid4()
    primary_party = uuid4()

    selected = resolver._select_party_id(
        [
            {"party_id": primary_party, "role": "parent", "is_primary": True},
            {"party_id": student_party, "role": "student", "is_primary": False},
        ]
    )

    assert selected == student_party


def test_customer_resolver_falls_back_to_primary_then_stable_sort() -> None:
    resolver = CustomerResolver()
    party_a = UUID("00000000-0000-0000-0000-00000000000a")
    party_b = UUID("00000000-0000-0000-0000-00000000000b")

    selected = resolver._select_party_id(
        [
            {"party_id": party_b, "role": "parent", "is_primary": False},
            {"party_id": party_a, "role": "parent", "is_primary": True},
        ]
    )

    assert selected == party_a


def test_alias_is_prefixed_and_trimmed() -> None:
    service = _service()
    alias = service._student_alias("Max Mustermann")
    assert alias == "🎒 Max Mustermann"

    trimmed = service._student_alias("A" * 80)
    assert trimmed.startswith("🎒 ")
    assert len(trimmed) == 32


def test_alias_rejects_blank_name() -> None:
    service = _service()
    with pytest.raises(StudentEnableError):
        service._student_alias("   ")


def test_autocomplete_shows_only_not_activated_non_bots() -> None:
    service = _service()

    async def fake_active_ids() -> set[int]:
        return {2}

    service._active_student_discord_ids = fake_active_ids  # type: ignore[method-assign]

    guild = _GuildStub(
        [
            _MemberStub(1, "alex"),
            _MemberStub(2, "albert"),
            _MemberStub(3, "bot-alex", bot=True),
            _MemberStub(4, "charlie"),
            _MemberStub(5, "alex2"),
        ]
    )
    interaction = _InteractionStub(guild)

    choices = asyncio.run(service.autocomplete_discord_name(interaction, "alex"))
    values = [c.value for c in choices]

    assert values == ["alex", "alex2"]


def test_autocomplete_is_capped_at_25_results() -> None:
    service = _service()

    async def fake_active_ids() -> set[int]:
        return set()

    service._active_student_discord_ids = fake_active_ids  # type: ignore[method-assign]

    members = [_MemberStub(i, f"anna{i}") for i in range(30)]
    interaction = _InteractionStub(_GuildStub(members))

    choices = asyncio.run(service.autocomplete_discord_name(interaction, "anna"))

    assert len(choices) == 25
