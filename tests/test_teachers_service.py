import asyncio

import pytest
from skillcore.db import Database

from skillbot.cogs.teachers.service import TeacherEnableError, TeacherEnableService
from skillbot.core.permissions import CommandEnvironmentService


class _RoleStub:
    def __init__(self, role_id: int, name: str):
        self.id = role_id
        self.name = name


class _MemberStub:
    def __init__(self, member_id: int, name: str, *, bot: bool = False, roles=None):
        self.id = member_id
        self.name = name
        self.bot = bot
        self.roles = roles or []


class _GuildStub:
    def __init__(self, members):
        self.members = members


class _InteractionStub:
    def __init__(self, guild):
        self.guild = guild


def _service() -> TeacherEnableService:
    db = Database.__new__(Database)  # lightweight placeholder; tests only call pure helper logic
    cmd_env_service = CommandEnvironmentService.__new__(CommandEnvironmentService)
    return TeacherEnableService(db, cmd_env_service)


def test_teacher_autocomplete_excludes_students_and_active_teachers() -> None:
    service = _service()

    async def fake_ids() -> tuple[set[int], set[int]]:
        return {2}, {3}

    service._teacher_and_student_discord_ids = fake_ids  # type: ignore[method-assign]

    guild = _GuildStub(
        [
            _MemberStub(1, "alex"),
            _MemberStub(2, "alexa"),
            _MemberStub(3, "alexb"),
            _MemberStub(4, "alexc", roles=[_RoleStub(55, "Schüler")]),
            _MemberStub(5, "bot-alex", bot=True),
        ]
    )

    choices = asyncio.run(service.autocomplete_discord_name(_InteractionStub(guild), "alex"))
    values = [c.value for c in choices]
    assert values == ["alex"]


def test_teacher_autocomplete_is_capped() -> None:
    service = _service()

    async def fake_ids() -> tuple[set[int], set[int]]:
        return set(), set()

    service._teacher_and_student_discord_ids = fake_ids  # type: ignore[method-assign]
    guild = _GuildStub([_MemberStub(i, f"anna{i}") for i in range(40)])

    choices = asyncio.run(service.autocomplete_discord_name(_InteractionStub(guild), "anna"))
    assert len(choices) == 25


def test_teacher_alias_is_prefixed_and_trimmed() -> None:
    service = _service()
    alias = service._teacher_alias("Max Mustermann")
    assert alias == "🎓 Max Mustermann"

    trimmed = service._teacher_alias("A" * 80)
    assert trimmed.startswith("🎓 ")
    assert len(trimmed) == 32


def test_teacher_alias_rejects_blank_name() -> None:
    service = _service()
    with pytest.raises(TeacherEnableError):
        service._teacher_alias("   ")
