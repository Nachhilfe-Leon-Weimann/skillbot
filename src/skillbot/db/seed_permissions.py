from __future__ import annotations

from skillcore.db import Database
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    MemberRole,
    PermissionGrant,
    PermissionGrantEffect,
    PermissionSubjectType,
)

DEFAULT_PERMISSION_GRANTS: tuple[tuple[PermissionSubjectType, str, str, PermissionGrantEffect, int], ...] = (
    (PermissionSubjectType.role, MemberRole.admin.value, "*", PermissionGrantEffect.allow, 1000),
    (PermissionSubjectType.role, MemberRole.teacher.value, "teachers.*", PermissionGrantEffect.allow, 200),
    (PermissionSubjectType.role, MemberRole.teacher.value, "students.*", PermissionGrantEffect.allow, 200),
)


async def seed_default_permission_grants(db: Database) -> None:
    async with db.session() as session:
        await seed_default_permission_grants_in_session(session)
        await session.commit()


async def seed_default_permission_grants_in_session(session: AsyncSession) -> None:
    existing_rows = await session.scalars(select(PermissionGrant))
    existing = {
        (
            grant.subject_type,
            grant.subject_key,
            grant.action_key,
            grant.effect,
        )
        for grant in existing_rows.all()
    }

    for subject_type, subject_key, action_key, effect, priority in DEFAULT_PERMISSION_GRANTS:
        signature = (subject_type, subject_key, action_key, effect)
        if signature in existing:
            continue

        session.add(
            PermissionGrant(
                subject_type=subject_type,
                subject_key=subject_key,
                action_key=action_key,
                effect=effect,
                priority=priority,
            )
        )
