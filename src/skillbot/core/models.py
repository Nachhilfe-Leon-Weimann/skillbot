from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class MemberRole(StrEnum):
    admin = "admin"
    teacher = "teacher"
    student = "student"


class PermissionSubjectType(StrEnum):
    role = "role"
    group = "group"
    user = "user"


class PermissionGrantEffect(StrEnum):
    allow = "allow"
    deny = "deny"


class CommandEnvKind(StrEnum):
    admin_cmd = "admin_cmd"
    teacher_cmd = "teacher_cmd"


@dataclass(frozen=True)
class BotUser:
    id: int
    discord_id: int
    full_name: str
    role: MemberRole


@dataclass(frozen=True)
class Teacher:
    user_id: int
    discord_id: int
    full_name: str
    teaching_category_id: int | None = None
    command_channel_id: int | None = None


@dataclass(frozen=True)
class Student:
    user_id: int
    discord_id: int
    full_name: str
    party_id: UUID
    teacher_user_id: int | None = None
    channel_id: int | None = None


@dataclass(frozen=True)
class PermissionPrincipal:
    discord_user_id: int
    user: BotUser | None = None
    group_keys: tuple[str, ...] = ()

    @property
    def role_key(self) -> str | None:
        return self.user.role.value if self.user is not None else None


@dataclass(frozen=True)
class PermissionSubject:
    type: PermissionSubjectType
    key: str


@dataclass(frozen=True)
class PermissionGrant:
    subject_type: PermissionSubjectType
    subject_key: str
    action_key: str
    effect: PermissionGrantEffect
    priority: int = 0


@dataclass(frozen=True)
class CommandEnvChannel:
    guild_id: int
    channel_id: int
    kind: CommandEnvKind
    owner_user_id: int | None = None
    active: bool = True


@dataclass(frozen=True)
class ActivateTeacherRequest:
    discord_id: int
    full_name: str
    teaching_category_id: int
    command_channel_id: int


@dataclass(frozen=True)
class ActivateStudentRequest:
    teacher_discord_id: int
    student_discord_id: int
    full_name: str
    customer_id: int

