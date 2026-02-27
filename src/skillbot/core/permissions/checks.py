from __future__ import annotations

import discord
from discord import app_commands

from .service import PermissionAction, PermissionDecision, PermissionService


class PermissionDenied(app_commands.CheckFailure):
    def __init__(self, decision: PermissionDecision):
        super().__init__(f"Dafür fehlt dir die Berechtigung: `{decision.action}`.")
        self.decision = decision


def _permission_service(interaction: discord.Interaction) -> PermissionService:
    service = getattr(interaction.client, "permission_service", None)
    if service is None:
        raise app_commands.CheckFailure("Permission service unavailable.")
    return service


def _store_decision(interaction: discord.Interaction, decision: PermissionDecision) -> None:
    interaction.extras["permission_decision"] = decision


def require_action(action: PermissionAction | str):
    async def predicate(interaction: discord.Interaction) -> bool:
        service = _permission_service(interaction)
        decision = await service.authorize(interaction, action)
        _store_decision(interaction, decision)

        if not decision.allowed:
            raise PermissionDenied(decision)
        return True

    return app_commands.check(predicate)


def require_any_action(*actions: PermissionAction | str):
    async def predicate(interaction: discord.Interaction) -> bool:
        if not actions:
            raise app_commands.CheckFailure("require_any_action needs at least one action.")

        service = _permission_service(interaction)
        decisions: list[PermissionDecision] = []

        for action in actions:
            decision = await service.authorize(interaction, action)
            decisions.append(decision)
            if decision.allowed:
                _store_decision(interaction, decision)
                return True

        denied = decisions[0]
        _store_decision(interaction, denied)
        raise PermissionDenied(denied)

    return app_commands.check(predicate)
