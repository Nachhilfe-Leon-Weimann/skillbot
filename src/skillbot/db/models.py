from enum import StrEnum

from sqlalchemy import BigInteger, Enum, ForeignKey, Index, Integer, MetaData, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    metadata = MetaData(schema="skillbot")


class MemberRole(StrEnum):
    admin = "admin"
    teacher = "teacher"
    student = "student"


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

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
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
