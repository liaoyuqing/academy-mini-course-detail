"""课程详情聚合：把课程、课期、讲师、评价、权益五块拼成一个响应，
并在这一层完成字段裁剪（企业能力卡、匿名评价、权益余额）。"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clients.crm_client import CrmClient, PUBLIC_CARD_FIELDS
from app.clients.enrollment_check import (
    EnrollmentCheckClient,
    EnrollmentCheckError,
    EnrollmentCheckRequest,
)
from app.core.logging import get_logger
from app.db.models import (
    AcademyCourse,
    AcademyCourseInstructor,
    AcademyEnrollment,
    AcademyEntitlement,
    AcademyInstructor,
    AcademyReview,
    AcademySession,
)
from app.domain.clock import to_iso_z, utc_now
from app.domain.signup_state import SignupState

logger = get_logger("course_detail")

ANONYMOUS_DISPLAY_NAME = "匿名学员"
RECENT_REVIEW_LIMIT = 3
ABILITY_TAG_LIMIT = 5


class CourseNotFound(Exception):
    """课程不存在、非 published 或被软删除；对外统一 404，不区分原因。"""


@dataclass(frozen=True)
class DetailContext:
    """一次请求的上下文：租户、当前会员、是否已登录。"""

    org_id: str | None
    site_id: str | None
    contact_id: str | None


def _round1(values: list[int]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 1)


def _sanitize_card(raw: dict | None) -> dict | None:
    """只放行四项公开字段，任何联系方式字段在进入 schema 前就被丢弃。"""
    if not raw:
        return None
    card: dict = {}
    for field in PUBLIC_CARD_FIELDS:
        if field == "ability_tags":
            tags = raw.get("ability_tags") or []
            if isinstance(tags, str):
                tags = [tags]
            cleaned = [str(tag).strip() for tag in tags if str(tag).strip()]
            if not cleaned:
                return None
            card[field] = cleaned[:ABILITY_TAG_LIMIT]
        else:
            value = raw.get(field)
            text = str(value).strip() if value is not None else ""
            if not text:
                return None
            card[field] = text
    return card


def _earliest_session_start(sessions: list[AcademySession]) -> str | None:
    if not sessions:
        return None
    return to_iso_z(min(item.start_at for item in sessions))


def _resolve_signup_state(
    client: EnrollmentCheckClient,
    course_id: str,
    session: AcademySession,
    contact_id: str | None,
) -> str:
    """透传资格服务结论；服务异常或返回未知值时降级为 pending_review 并留日志。"""
    request = EnrollmentCheckRequest(
        course_id=course_id,
        session_id=str(session.id),
        contact_id=contact_id,
        capacity=session.capacity,
        seats_taken=session.seats_taken,
        waitlist_enabled=session.waitlist_enabled,
        signup_mode=session.signup_mode,
        session_status=session.status,
        start_at=to_iso_z(session.start_at) or "",
        end_at=to_iso_z(session.end_at) or "",
    )
    try:
        return client.resolve(request)
    except EnrollmentCheckError as exc:
        logger.warning(
            "signup_state_degraded course_id=%s session_id=%s error=%s fallback=%s",
            course_id,
            session.id,
            exc,
            SignupState.PENDING_REVIEW.value,
        )
        return SignupState.PENDING_REVIEW.value


def parse_course_id(course_id: str) -> uuid.UUID:
    """路径参数必须是合法 UUID；不合法与「不存在」同口径，一律 404。"""
    try:
        return uuid.UUID(str(course_id))
    except (ValueError, AttributeError, TypeError) as exc:
        raise CourseNotFound(str(course_id)) from exc


def _load_course(db: Session, course_id: str, ctx: DetailContext) -> AcademyCourse:
    course_uuid = parse_course_id(course_id)
    stmt = select(AcademyCourse).where(
        AcademyCourse.id == course_uuid,
        AcademyCourse.status == "published",
        AcademyCourse.deleted_at.is_(None),
    )
    course = db.execute(stmt).scalar_one_or_none()
    if course is None:
        raise CourseNotFound(course_id)
    if ctx.org_id and str(course.org_id) != ctx.org_id:
        raise CourseNotFound(course_id)
    if ctx.site_id and str(course.site_id) != ctx.site_id:
        raise CourseNotFound(course_id)
    return course


def _load_open_sessions(db: Session, course: AcademyCourse, now) -> list[AcademySession]:
    """未结束课期 = end_at 晚于当前时间；按 start_at 升序返回。"""
    stmt = (
        select(AcademySession)
        .where(
            AcademySession.course_id == course.id,
            AcademySession.deleted_at.is_(None),
            AcademySession.end_at > now,
        )
        .order_by(AcademySession.start_at.asc(), AcademySession.id.asc())
    )
    return list(db.execute(stmt).scalars().all())


def _load_instructors(db: Session, course: AcademyCourse) -> list[AcademyInstructor]:
    stmt = (
        select(AcademyInstructor)
        .join(
            AcademyCourseInstructor,
            AcademyCourseInstructor.instructor_id == AcademyInstructor.id,
        )
        .where(
            AcademyCourseInstructor.course_id == course.id,
            AcademyCourseInstructor.deleted_at.is_(None),
            AcademyInstructor.deleted_at.is_(None),
        )
        .order_by(AcademyCourseInstructor.sort_order.asc(), AcademyInstructor.display_name.asc())
    )
    return list(db.execute(stmt).scalars().all())


def _build_review_summary(db: Session, course: AcademyCourse) -> dict:
    stmt = select(AcademyReview).where(
        AcademyReview.course_id == course.id,
        AcademyReview.visible.is_(True),
        AcademyReview.deleted_at.is_(None),
    )
    reviews = list(db.execute(stmt).scalars().all())
    visible_count = len(reviews)
    overall = [review.rating for review in reviews]
    content_scores = [review.rating_content for review in reviews]
    instructor_scores = [review.rating_instructor for review in reviews]
    service_scores = [review.rating_service for review in reviews]
    recent_sorted = sorted(reviews, key=lambda item: item.created_at, reverse=True)[:RECENT_REVIEW_LIMIT]
    recent = []
    for review in recent_sorted:
        recent.append(
            {
                "content": review.content,
                "rating": review.rating,
                "created_at": to_iso_z(review.created_at),
                "author_name": ANONYMOUS_DISPLAY_NAME if review.anonymous else review.author_name,
            }
        )
    return {
        "visible_count": visible_count,
        "overall_avg": _round1(overall),
        "avg_content": _round1(content_scores),
        "avg_instructor": _round1(instructor_scores),
        "avg_service": _round1(service_scores),
        "recent": recent,
    }


def _load_entitlement(db: Session, course: AcademyCourse, ctx: DetailContext) -> int | None:
    """fee_mode=entitlement 才返回余额；其余模式该键不出现。"""
    if course.fee_mode != "entitlement":
        return None
    if not ctx.contact_id:
        return 0
    try:
        contact_uuid = uuid.UUID(str(ctx.contact_id))
    except (ValueError, AttributeError, TypeError):
        logger.warning("invalid_contact_id value=%s", ctx.contact_id)
        return 0
    stmt = select(AcademyEntitlement).where(
        AcademyEntitlement.contact_id == contact_uuid,
        AcademyEntitlement.deleted_at.is_(None),
    )
    if course.category:
        stmt = stmt.where(
            (AcademyEntitlement.course_category == course.category)
            | (AcademyEntitlement.course_category.is_(None))
        )
    entitlements = list(db.execute(stmt).scalars().all())
    if not entitlements:
        return 0
    now = utc_now()
    valid = [
        item for item in entitlements if item.valid_until is None or item.valid_until > now
    ]
    return max(0, sum(item.remaining_cents for item in valid))


def build_course_detail(
    db: Session,
    course_id: str,
    ctx: DetailContext,
    crm_client: CrmClient,
    enrollment_client: EnrollmentCheckClient,
    now=None,
) -> dict:
    """返回可直接 JSON 化的字典；调用方负责按 None 裁剪可选键。"""
    now = now or utc_now()
    course = _load_course(db, course_id, ctx)
    sessions = _load_open_sessions(db, course, now)
    instructors = _load_instructors(db, course)

    session_items = []
    for session in sessions:
        seats_remaining = max(0, session.capacity - session.seats_taken)
        session_items.append(
            {
                "session_id": str(session.id),
                "label": session.label,
                "start_at": to_iso_z(session.start_at),
                "end_at": to_iso_z(session.end_at),
                "room_name": session.room_name,
                "seats_remaining": seats_remaining,
                "waitlist_count": session.waitlist_count,
                "signup_state": _resolve_signup_state(
                    enrollment_client, str(course.id), session, ctx.contact_id
                ),
            }
        )

    instructor_items = []
    for instructor in instructors:
        item = {
            "instructor_id": str(instructor.id),
            "display_name": instructor.display_name,
            "headline": instructor.headline,
            "bio": instructor.bio,
            "avatar_url": instructor.avatar_url,
            "role": instructor.role,
            "show_company_card": bool(instructor.show_company_card),
            "company_card": None,
        }
        if instructor.show_company_card and instructor.crm_company_id:
            raw = crm_client.fetch_company_card(instructor.crm_company_id)
            item["company_card"] = _sanitize_card(raw)
        instructor_items.append(item)

    return {
        "course_id": str(course.id),
        "title": course.title,
        "subtitle": course.subtitle,
        "category": course.category,
        "intro": course.intro,
        "outline": list(course.outline or []),
        "outcomes": list(course.outcomes or []),
        "cover_url": course.cover_url,
        "fee_mode": course.fee_mode,
        "sessions": session_items,
        "instructors": instructor_items,
        "review_summary": _build_review_summary(db, course),
        "remaining": _load_entitlement(db, course, ctx),
    }


def list_enrollments(db: Session, session_id: str, contact_id: str) -> list[AcademyEnrollment]:
    """供其他工单复用的报名查询；本单不对外暴露。"""
    stmt = select(AcademyEnrollment).where(
        AcademyEnrollment.session_id == session_id,
        AcademyEnrollment.contact_id == contact_id,
        AcademyEnrollment.deleted_at.is_(None),
    )
    return list(db.execute(stmt).scalars().all())

