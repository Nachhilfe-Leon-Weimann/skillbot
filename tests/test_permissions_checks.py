import asyncio
import logging

import pytest

from skillbot.core.app_command_logger import AppCommandLogger, AppCommandLogPolicy
from skillbot.core.permissions.checks import PermissionDenied, require_action, require_any_action
from skillbot.core.permissions.service import PermissionAction, PermissionDecision


class _ServiceStub:
    def __init__(self, decisions: dict[str, PermissionDecision]):
        self.decisions = decisions
        self.calls: list[str] = []

    async def authorize(self, interaction, action, *, context=None):
        del interaction, context
        action_key = action.value if isinstance(action, PermissionAction) else str(action)
        self.calls.append(action_key)
        return self.decisions[action_key]


class _ClientStub:
    def __init__(self, service):
        self.permission_service = service


class _UserStub:
    id = 42

    def __str__(self) -> str:
        return "stub-user"


class _GuildStub:
    id = 777


class _InteractionStub:
    def __init__(self, service):
        self.client = _ClientStub(service)
        self.extras: dict[str, object] = {}
        self.user = _UserStub()
        self.guild = _GuildStub()


class _CommandStub:
    qualified_name = "students enable"


def _decision(*, allowed: bool, action: str) -> PermissionDecision:
    return PermissionDecision(
        allowed=allowed,
        action=action,
        reason="test",
        source="test",
        matched_subject="role:teacher",
    )


def test_require_action_allows_and_stores_decision() -> None:
    service = _ServiceStub({"students.enable": _decision(allowed=True, action="students.enable")})
    interaction = _InteractionStub(service)

    @require_action(PermissionAction.STUDENTS_ENABLE)
    async def command(_interaction): ...

    predicate = command.__discord_app_commands_checks__[0]
    result = asyncio.run(predicate(interaction))

    assert result is True
    assert interaction.extras["permission_decision"].allowed is True


def test_require_action_denied_raises_check_failure() -> None:
    service = _ServiceStub({"students.enable": _decision(allowed=False, action="students.enable")})
    interaction = _InteractionStub(service)

    @require_action(PermissionAction.STUDENTS_ENABLE)
    async def command(_interaction): ...

    predicate = command.__discord_app_commands_checks__[0]

    with pytest.raises(PermissionDenied) as exc:
        asyncio.run(predicate(interaction))

    assert "students.enable" in str(exc.value)
    assert interaction.extras["permission_decision"].allowed is False


def test_require_any_action_uses_first_allow() -> None:
    service = _ServiceStub(
        {
            "teachers.test": _decision(allowed=False, action="teachers.test"),
            "students.enable": _decision(allowed=True, action="students.enable"),
        }
    )
    interaction = _InteractionStub(service)

    @require_any_action("teachers.test", "students.enable")
    async def command(_interaction): ...

    predicate = command.__discord_app_commands_checks__[0]
    result = asyncio.run(predicate(interaction))

    assert result is True
    assert service.calls == ["teachers.test", "students.enable"]
    assert interaction.extras["permission_decision"].action == "students.enable"


def test_logger_adds_permission_fields_for_denied_checks(caplog: pytest.LogCaptureFixture) -> None:
    decision = _decision(allowed=False, action="students.enable")
    interaction = _InteractionStub(_ServiceStub({}))
    interaction.extras["permission_decision"] = decision

    logger = AppCommandLogger(policy=AppCommandLogPolicy())
    error = PermissionDenied(decision)

    with caplog.at_level(logging.WARNING):
        asyncio.run(logger.log_error(interaction, _CommandStub(), error))

    record = caplog.records[-1]
    assert getattr(record, "permission_action", None) == "students.enable"
    assert getattr(record, "permission_allowed", None) is False
    assert getattr(record, "permission_source", None) == "test"
