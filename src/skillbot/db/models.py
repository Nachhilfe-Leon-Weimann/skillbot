from enum import StrEnum
from uuid import UUID

from sqlalchemy import BigInteger, Enum, ForeignKey, Index, Integer, MetaData, String, UniqueConstraint, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    metadata = MetaData(schema="skillbot")


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


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("discord_id", name="uq_users_discord_id"),
        Index("ix_users_role", "role"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    discord_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    full_name: Mapped[str] = mapped_column(String(200), nullable=False)

    role: Mapped[MemberRole] = mapped_column(
        Enum(MemberRole, name="member_role"),
        nullable=False,
    )

    teacher_profile: Mapped["TeacherProfile | None"] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    student_profile: Mapped["StudentProfile | None"] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )


class TeacherProfile(Base):
    __tablename__ = "teacher_profiles"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )

    teaching_category_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    user: Mapped["User"] = relationship(back_populates="teacher_profile")


class StudentProfile(Base):
    __tablename__ = "student_profiles"
    __table_args__ = (UniqueConstraint("party_id", name="uq_student_profiles_party_id"),)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    party_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("core.party.id", ondelete="RESTRICT"),
        nullable=False,
    )

    user: Mapped["User"] = relationship(back_populates="student_profile")


class TeacherStudent(Base):
    """Relationsshiop teacher <-> student. Channel belongs to the relationship"""

    __tablename__ = "teacher_students"
    __table_args__ = (
        UniqueConstraint("student_user_id", name="uq_teacher_students_student_one_teacher"),
        Index("ix_teacher_students_teacher", "teacher_user_id"),
        UniqueConstraint("channel_id", name="uq_teacher_students_channel_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    teacher_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    student_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class PermissionGroup(Base):
    __tablename__ = "permission_groups"
    __table_args__ = (
        UniqueConstraint("key", name="uq_permission_groups_key"),
        Index("ix_permission_groups_active", "active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    active: Mapped[bool] = mapped_column(nullable=False, default=True)

    members: Mapped[list["PermissionGroupMember"]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
    )


class PermissionGroupMember(Base):
    __tablename__ = "permission_group_members"
    __table_args__ = (UniqueConstraint("group_id", "user_id", name="uq_permission_group_members_group_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(
        ForeignKey("permission_groups.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    group: Mapped["PermissionGroup"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship()


class PermissionGrant(Base):
    __tablename__ = "permission_grants"
    __table_args__ = (
        Index("ix_permission_grants_subject", "subject_type", "subject_key"),
        Index("ix_permission_grants_action_key", "action_key"),
        Index("ix_permission_grants_subject_action", "subject_type", "subject_key", "action_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_type: Mapped[PermissionSubjectType] = mapped_column(
        Enum(PermissionSubjectType, name="permission_subject_type"),
        nullable=False,
    )
    subject_key: Mapped[str] = mapped_column(String(120), nullable=False)
    action_key: Mapped[str] = mapped_column(String(180), nullable=False)
    effect: Mapped[PermissionGrantEffect] = mapped_column(
        Enum(PermissionGrantEffect, name="permission_grant_effect"),
        nullable=False,
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class CommandEnvChannel(Base):
    __tablename__ = "command_env_channels"
    __table_args__ = (
        UniqueConstraint("channel_id", name="uq_command_env_channels_channel_id"),
        Index("ix_command_env_channels_kind_active", "kind", "active"),
        Index("ix_command_env_channels_owner_kind_active", "owner_user_id", "kind", "active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    kind: Mapped[CommandEnvKind] = mapped_column(
        Enum(CommandEnvKind, name="command_env_kind"),
        nullable=False,
    )
    owner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    active: Mapped[bool] = mapped_column(nullable=False, default=True)

    owner_user: Mapped["User | None"] = relationship()
