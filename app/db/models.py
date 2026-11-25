"""学院域数据模型。业务表统一含 id / org_id / site_id / created_at / created_by /
updated_at / deleted_at（软删除），金额一律用「分」存整数。"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import json_list, utc_datetime, uuid_fk, uuid_pk
from app.domain.clock import utc_now


class OrgScopedMixin:
    """所有业务表共用的租户与审计列。"""

    id: Mapped[uuid.UUID] = uuid_pk()
    org_id: Mapped[uuid.UUID] = uuid_fk()
    site_id: Mapped[uuid.UUID] = uuid_fk()
    created_at: Mapped[datetime] = utc_datetime(nullable=False)
    created_by: Mapped[uuid.UUID] = uuid_fk(nullable=True)
    updated_at: Mapped[datetime] = utc_datetime(nullable=False)
    deleted_at: Mapped[datetime | None] = utc_datetime(nullable=True, index=True)


class AcademyCourse(OrgScopedMixin, Base):
    __tablename__ = "academy_course"

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String(200), nullable=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    intro: Mapped[str | None] = mapped_column(Text, nullable=True)
    outline: Mapped[list] = json_list()
    outcomes: Mapped[list] = json_list()
    cover_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    fee_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="free")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")


class AcademyInstructor(OrgScopedMixin, Base):
    __tablename__ = "academy_instructor"

    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    headline: Mapped[str | None] = mapped_column(String(200), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="instructor")
    show_company_card: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    crm_company_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    contact_id: Mapped[uuid.UUID | None] = uuid_fk(nullable=True)


class AcademyCourseInstructor(Base):
    __tablename__ = "academy_course_instructor"

    id: Mapped[uuid.UUID] = uuid_pk()
    course_id: Mapped[uuid.UUID] = uuid_fk()
    instructor_id: Mapped[uuid.UUID] = uuid_fk()
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    org_id: Mapped[uuid.UUID] = uuid_fk()
    site_id: Mapped[uuid.UUID] = uuid_fk()
    created_at: Mapped[datetime] = utc_datetime(nullable=False)
    created_by: Mapped[uuid.UUID] = uuid_fk(nullable=True)
    updated_at: Mapped[datetime] = utc_datetime(nullable=False)
    deleted_at: Mapped[datetime | None] = utc_datetime(nullable=True, index=True)

    __table_args__ = (UniqueConstraint("course_id", "instructor_id", name="uq_course_instructor"),)


class AcademySession(OrgScopedMixin, Base):
    __tablename__ = "academy_session"

    course_id: Mapped[uuid.UUID] = uuid_fk()
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    start_at: Mapped[datetime] = utc_datetime(nullable=False, index=True)
    end_at: Mapped[datetime] = utc_datetime(nullable=False, index=True)
    signup_open_at: Mapped[datetime] = utc_datetime(nullable=False)
    signup_deadline: Mapped[datetime] = utc_datetime(nullable=False)
    room_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    seats_taken: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    waitlist_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    waitlist_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    signup_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="instant")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="scheduled")


class AcademyEnrollment(OrgScopedMixin, Base):
    __tablename__ = "academy_enrollment"

    session_id: Mapped[uuid.UUID] = uuid_fk()
    contact_id: Mapped[uuid.UUID] = uuid_fk()
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="signed_up")


class AcademyReview(OrgScopedMixin, Base):
    __tablename__ = "academy_review"

    course_id: Mapped[uuid.UUID] = uuid_fk()
    contact_id: Mapped[uuid.UUID] = uuid_fk()
    author_name: Mapped[str] = mapped_column(String(100), nullable=False)
    anonymous: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    rating_content: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    rating_instructor: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    rating_service: Mapped[int] = mapped_column(Integer, nullable=False, default=5)


class AcademyEntitlement(OrgScopedMixin, Base):
    __tablename__ = "academy_entitlement"

    contact_id: Mapped[uuid.UUID] = uuid_fk()
    course_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    remaining_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_until: Mapped[datetime | None] = utc_datetime(nullable=True)


def new_id() -> uuid.UUID:
    return uuid.uuid4()


def touch(rows: list) -> list:
    """填充审计列的便捷函数，仅供 seed 与测试构造数据使用。"""
    now = utc_now()
    for row in rows:
        if getattr(row, "id", None) is None:
            row.id = new_id()
        if getattr(row, "created_at", None) is None:
            row.created_at = now
        if getattr(row, "updated_at", None) is None:
            row.updated_at = now
    return rows

