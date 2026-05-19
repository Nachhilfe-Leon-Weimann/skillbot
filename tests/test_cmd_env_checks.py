import asyncio

import pytest

from skillbot.core.models import CommandEnvKind
from skillbot.core.permissions.checks import CmdEnvDenied, require_cmd_env
from skillbot.core.permissions.cmd_env import CmdEnvDecision


class _CommandEnvServiceStub:
    def __init__(self, decision: CmdEnvDecision):
        self.decision = decision

    async def authorize(self, interaction, *, kind, owner_bound=False):
        del interaction, kind, owner_bound
        return self.decision


class _ClientStub:
    def __init__(self, env_service):
        self.command_env_service = env_service


class _InteractionStub:
    def __init__(self, env_service):
        self.client = _ClientStub(env_service)
        self.extras: dict[str, object] = {}


def test_require_cmd_env_allows_and_stores_decision() -> None:
    decision = CmdEnvDecision(allowed=True, kind="admin_cmd", reason="ok", channel_id=123, owner_user_id=None)
    interaction = _InteractionStub(_CommandEnvServiceStub(decision))

    @require_cmd_env(CommandEnvKind.admin_cmd)
    async def command(_interaction): ...

    predicate = command.__discord_app_commands_checks__[0]
    result = asyncio.run(predicate(interaction))

    assert result is True
    assert interaction.extras["cmd_env_decision"].allowed is True


def test_require_cmd_env_denied_raises() -> None:
    decision = CmdEnvDecision(allowed=False, kind="teacher_cmd", reason="not whitelisted", channel_id=999)
    interaction = _InteractionStub(_CommandEnvServiceStub(decision))

    @require_cmd_env(CommandEnvKind.teacher_cmd, owner_bound=True)
    async def command(_interaction): ...

    predicate = command.__discord_app_commands_checks__[0]
    with pytest.raises(CmdEnvDenied):
        asyncio.run(predicate(interaction))
