from skillbot.core.models import PermissionGrant, PermissionGrantEffect, PermissionSubjectType
from skillbot.core.permissions.service import PermissionService


def _grant(
    *,
    subject_type: PermissionSubjectType,
    subject_key: str,
    action_key: str,
    effect: PermissionGrantEffect,
    priority: int = 0,
) -> PermissionGrant:
    return PermissionGrant(
        subject_type=subject_type,
        subject_key=subject_key,
        action_key=action_key,
        effect=effect,
        priority=priority,
    )


def _service() -> PermissionService:
    return PermissionService()


def test_user_allow_overrides_role_deny() -> None:
    service = _service()
    decision = service._evaluate_grants(
        "students.enable",
        [
            _grant(
                subject_type=PermissionSubjectType.role,
                subject_key="teacher",
                action_key="students.enable",
                effect=PermissionGrantEffect.deny,
                priority=99,
            ),
            _grant(
                subject_type=PermissionSubjectType.user,
                subject_key="123",
                action_key="students.enable",
                effect=PermissionGrantEffect.allow,
            ),
        ],
    )

    assert decision.allowed is True
    assert decision.source == "user_group_grant"
    assert decision.matched_subject == "user:123"


def test_group_deny_overrides_role_allow() -> None:
    service = _service()
    decision = service._evaluate_grants(
        "students.add",
        [
            _grant(
                subject_type=PermissionSubjectType.role,
                subject_key="teacher",
                action_key="students.add",
                effect=PermissionGrantEffect.allow,
            ),
            _grant(
                subject_type=PermissionSubjectType.group,
                subject_key="admins",
                action_key="students.add",
                effect=PermissionGrantEffect.deny,
            ),
        ],
    )

    assert decision.allowed is False
    assert decision.source == "user_group_grant"
    assert decision.matched_subject == "group:admins"


def test_wildcard_matches_action() -> None:
    service = _service()
    decision = service._evaluate_grants(
        "students.enable",
        [
            _grant(
                subject_type=PermissionSubjectType.role,
                subject_key="teacher",
                action_key="students.*",
                effect=PermissionGrantEffect.allow,
            )
        ],
    )

    assert decision.allowed is True
    assert decision.matched_subject == "role:teacher"


def test_unmatched_action_is_denied() -> None:
    service = _service()
    decision = service._evaluate_grants("unknown.action", [])

    assert decision.allowed is False
    assert decision.source == "default_deny"
    assert decision.matched_subject is None


def test_priority_wins_within_same_subject_type() -> None:
    service = _service()
    decision = service._evaluate_grants(
        "teachers.test",
        [
            _grant(
                subject_type=PermissionSubjectType.role,
                subject_key="teacher",
                action_key="teachers.test",
                effect=PermissionGrantEffect.allow,
                priority=10,
            ),
            _grant(
                subject_type=PermissionSubjectType.role,
                subject_key="teacher",
                action_key="teachers.test",
                effect=PermissionGrantEffect.deny,
                priority=20,
            ),
        ],
    )

    assert decision.allowed is False
    assert "priority=20" in decision.reason
