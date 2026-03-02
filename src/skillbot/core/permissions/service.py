from dataclasses import dataclass
from enum import StrEnum

import discord
from skillcore.db import Database
from sqlalchemy import and_, or_, select

from skillbot.core.discord_roles import DiscordRoleResolver
from skillbot.db.models import (
    MemberRole,
    PermissionGrant,
    PermissionGrantEffect,
    PermissionGroup,
    PermissionGroupMember,
    PermissionSubjectType,
    User,
)


class PermissionAction(StrEnum):
    TEACHERS_ENABLE = "teachers.enable"
    TEACHERS_TEST = "teachers.test"
    STUDENTS_ENABLE = "students.enable"


class PermissionEffect(StrEnum):
    allow = "allow"
    deny = "deny"


@dataclass(frozen=True)
class PermissionDecision:
    allowed: bool
    action: str
    reason: str
    source: str
    matched_subject: str | None


@dataclass(frozen=True)
class _PrincipalContext:
    discord_user_id: int
    user_subject_key: str
    group_subject_keys: tuple[str, ...]
    role_subject_key: str | None


@dataclass(frozen=True)
class _MatchedGrant:
    grant: PermissionGrant
    specificity: int


class PermissionService:
    def __init__(self, db: Database):
        self._db = db
        self._role_resolver = DiscordRoleResolver()

    async def authorize(
        self,
        interaction: discord.Interaction,
        action: PermissionAction | str,
        *,
        context: dict | None = None,
    ) -> PermissionDecision:
        del context  # currently unused, reserved for future resource-scoped checks.
        action_key = self._normalize_action(action)

        principal = await self._resolve_principals(interaction)
        if principal is None:
            return PermissionDecision(
                allowed=False,
                action=action_key,
                reason="Interaction user is missing.",
                source="default_deny",
                matched_subject=None,
            )

        grants = await self._load_grants(principal)
        return self._evaluate_grants(action_key, grants)

    async def can(
        self,
        interaction: discord.Interaction,
        action: PermissionAction | str,
        *,
        context: dict | None = None,
    ) -> bool:
        decision = await self.authorize(interaction, action, context=context)
        return decision.allowed

    async def can_any(
        self,
        interaction: discord.Interaction,
        actions: list[PermissionAction | str],
        *,
        context: dict | None = None,
    ) -> bool:
        for action in actions:
            if await self.can(interaction, action, context=context):
                return True
        return False

    def _normalize_action(self, action: PermissionAction | str) -> str:
        if isinstance(action, PermissionAction):
            return action.value
        return str(action).strip()

    async def _resolve_principals(self, interaction: discord.Interaction) -> _PrincipalContext | None:
        user = interaction.user
        if user is None:
            return None

        discord_user_id = getattr(user, "id", None)
        if discord_user_id is None:
            return None

        user_subject_key = str(discord_user_id)
        group_subject_keys: tuple[str, ...] = ()
        role_subject_key: str | None = None

        async with self._db.session() as session:
            db_user = await session.scalar(select(User).where(User.discord_id == discord_user_id))

            if db_user is not None:
                role_subject_key = db_user.role.value
                group_keys = await session.scalars(
                    select(PermissionGroup.key)
                    .join(PermissionGroupMember, PermissionGroupMember.group_id == PermissionGroup.id)
                    .where(
                        PermissionGroupMember.user_id == db_user.id,
                        PermissionGroup.active.is_(True),
                    )
                )
                group_subject_keys = tuple(group_keys.all())

        if role_subject_key is None:
            role_subject_key = self._fallback_role_from_discord(user)

        return _PrincipalContext(
            discord_user_id=discord_user_id,
            user_subject_key=user_subject_key,
            group_subject_keys=group_subject_keys,
            role_subject_key=role_subject_key,
        )

    def _fallback_role_from_discord(self, user: discord.abc.User) -> str | None:
        if not isinstance(user, discord.Member):
            return None

        role = self._role_resolver.member_primary_role(user)
        return role.value if isinstance(role, MemberRole) else None

    async def _load_grants(self, principal: _PrincipalContext) -> list[PermissionGrant]:
        predicates = [
            and_(
                PermissionGrant.subject_type == PermissionSubjectType.user,
                PermissionGrant.subject_key == principal.user_subject_key,
            )
        ]

        for group_key in principal.group_subject_keys:
            predicates.append(
                and_(
                    PermissionGrant.subject_type == PermissionSubjectType.group,
                    PermissionGrant.subject_key == group_key,
                )
            )

        if principal.role_subject_key:
            predicates.append(
                and_(
                    PermissionGrant.subject_type == PermissionSubjectType.role,
                    PermissionGrant.subject_key == principal.role_subject_key,
                )
            )

        async with self._db.session() as session:
            result = await session.scalars(select(PermissionGrant).where(or_(*predicates)))
            return list(result.all())

    def _evaluate_grants(self, action_key: str, grants: list[PermissionGrant]) -> PermissionDecision:
        user_group_matches: list[_MatchedGrant] = []
        role_matches: list[_MatchedGrant] = []

        for grant in grants:
            specificity = self._specificity(grant.action_key, action_key)
            if specificity < 0:
                continue

            match = _MatchedGrant(grant=grant, specificity=specificity)
            if grant.subject_type in (PermissionSubjectType.user, PermissionSubjectType.group):
                user_group_matches.append(match)
            elif grant.subject_type == PermissionSubjectType.role:
                role_matches.append(match)

        if user_group_matches:
            winner = self._pick_best_match(user_group_matches)
            return self._decision_from_match(action_key, winner, "user_group_grant")

        if role_matches:
            winner = self._pick_best_match(role_matches)
            return self._decision_from_match(action_key, winner, "role_grant")

        return PermissionDecision(
            allowed=False,
            action=action_key,
            reason="No matching permission grant found.",
            source="default_deny",
            matched_subject=None,
        )

    def _pick_best_match(self, matches: list[_MatchedGrant]) -> _MatchedGrant:
        subject_rank = {
            PermissionSubjectType.user: 2,
            PermissionSubjectType.group: 1,
            PermissionSubjectType.role: 0,
        }

        return max(
            matches,
            key=lambda m: (
                subject_rank[m.grant.subject_type],
                m.specificity,
                m.grant.priority,
                1 if m.grant.effect == PermissionGrantEffect.deny else 0,
            ),
        )

    def _decision_from_match(self, action_key: str, match: _MatchedGrant, source: str) -> PermissionDecision:
        grant = match.grant
        effect = PermissionEffect(grant.effect.value)
        return PermissionDecision(
            allowed=effect == PermissionEffect.allow,
            action=action_key,
            reason=(
                f"Matched {grant.subject_type.value}:{grant.subject_key} "
                f"for {grant.action_key} ({effect.value}, priority={grant.priority})."
            ),
            source=source,
            matched_subject=f"{grant.subject_type.value}:{grant.subject_key}",
        )

    def _specificity(self, grant_action: str, action_key: str) -> int:
        if grant_action == action_key:
            return 2
        if grant_action == "*":
            return 0
        if grant_action.endswith(".*") and action_key.startswith(grant_action[:-1]):
            return 1
        return -1
