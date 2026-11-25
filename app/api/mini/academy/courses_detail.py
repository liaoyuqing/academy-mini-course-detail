"""GET /api/mini/academy/courses/{id} —— 小程序课程详情。

响应组装顺序：课程（不存在/非 published/软删除 -> 404）-> 未结束课期（start_at 升序）
-> 讲师（show_company_card=true 才挂 company_card）-> 评价摘要 -> 权益余额。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import (
    get_crm_client,
    get_current_contact_id,
    get_db,
    get_enrollment_client,
)
from app.clients.crm_client import CrmClient
from app.clients.enrollment_check import EnrollmentCheckClient
from app.schemas.academy_course_detail import AcademyCourseDetail
from app.services.academy_course_detail import (
    CourseNotFound,
    DetailContext,
    build_course_detail,
)

router = APIRouter(prefix="/api/mini/academy", tags=["mini-academy"])


def _drop_absent_optional_keys(payload: dict) -> dict:
    """可选键在「不需要」时整体消失，而不是留一个 null：
    - 讲师 show_company_card=false -> 不含 company_card
    - fee_mode != entitlement -> 不含 remaining"""
    for instructor in payload.get("instructors", []):
        if not instructor.get("show_company_card"):
            instructor.pop("company_card", None)
        elif instructor.get("company_card") is None:
            instructor.pop("company_card", None)
    if payload.get("fee_mode") != "entitlement":
        payload.pop("remaining", None)
    return payload


@router.get(
    "/courses/{course_id}",
    response_model=AcademyCourseDetail,
    response_model_exclude_none=True,
    summary="小程序课程详情：课期、讲师与企业能力卡、评价摘要、权益余额",
    responses={404: {"description": "课程不存在、非 published 或已软删除"}},
)
def get_course_detail(
    course_id: str,
    db: Session = Depends(get_db),
    contact_id: str | None = Depends(get_current_contact_id),
    crm_client: CrmClient = Depends(get_crm_client),
    enrollment_client: EnrollmentCheckClient = Depends(get_enrollment_client),
) -> AcademyCourseDetail:
    ctx = DetailContext(org_id=None, site_id=None, contact_id=contact_id)
    try:
        payload = build_course_detail(db, course_id, ctx, crm_client, enrollment_client)
    except CourseNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="course not found",
        ) from None
    payload = _drop_absent_optional_keys(payload)
    return AcademyCourseDetail.model_validate(payload)


@router.get("/healthz", summary="学院子模块健康检查")
def healthz() -> dict:
    return {"status": "ok", "module": "academy"}

