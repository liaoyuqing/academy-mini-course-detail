"""GET /api/mini/academy/courses/{id} 的响应 schema。

字段裁剪规则写在这里而不是散落在路由里：
- `company_card` 仅在讲师 `show_company_card=true` 时存在，值为 `None` 的键在输出时整体剔除；
- 匿名评价只输出 `content / rating / created_at / author_name` 四个键，`contact_id` 永不进入 schema；
- `remaining` 仅在 `fee_mode=entitlement` 时存在，单位为「分」。
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


SignupStateLiteral = Literal[
    "can_signup",
    "signed_up",
    "waitlisted",
    "waitlist_available",
    "pending_review",
    "need_auth",
    "need_member",
    "no_entitlement",
    "not_open",
    "closed",
    "finished",
    "application",
]


class CompanyCard(BaseModel):
    """企业能力卡摘要。只保留四项公开信息，联系方式一律不进入本 schema。"""

    model_config = ConfigDict(extra="forbid")

    short_name: str = Field(description="企业简称")
    industry: str = Field(description="所属行业")
    ability_tags: list[str] = Field(
        default_factory=list,
        max_length=5,
        description="能力供给标签，最多 5 个",
    )
    summary: str = Field(description="一句话简介")


class InstructorItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instructor_id: str
    display_name: str
    headline: str | None = None
    bio: str | None = None
    avatar_url: str | None = None
    role: str = Field(description="主讲 / 助教 / 嘉宾等")
    show_company_card: bool = Field(description="是否展示企业能力卡")
    company_card: CompanyCard | None = Field(
        default=None,
        description="仅当 show_company_card=true 时存在；false 时该键不出现在响应中",
    )


class SessionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    label: str
    start_at: str = Field(description="ISO8601 UTC，带 Z")
    end_at: str = Field(description="ISO8601 UTC，带 Z")
    room_name: str | None = None
    seats_remaining: int = Field(ge=0, description="剩余名额")
    waitlist_count: int = Field(ge=0, description="候补人数")
    signup_state: SignupStateLiteral = Field(description="报名资格校验服务给出的 12 种取值之一")


class ReviewItem(BaseModel):
    """评价条目。匿名评价的 author_name 固定为「匿名学员」，本 schema 不含 contact_id。"""

    model_config = ConfigDict(extra="forbid")

    content: str
    rating: int = Field(ge=1, le=5)
    created_at: str
    author_name: str


class ReviewSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    visible_count: int = Field(ge=0, description="visible 评价数")
    overall_avg: float | None = Field(default=None, description="总体均分，一位小数")
    avg_content: float | None = Field(default=None, description="内容分项均分")
    avg_instructor: float | None = Field(default=None, description="讲师分项均分")
    avg_service: float | None = Field(default=None, description="服务分项均分")
    recent: list[ReviewItem] = Field(default_factory=list, description="最近 3 条 visible 评价")


class AcademyCourseDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_id: str
    title: str
    subtitle: str | None = None
    category: str | None = None
    intro: str | None = None
    outline: list[str] = Field(default_factory=list)
    outcomes: list[str] = Field(default_factory=list)
    cover_url: str | None = None
    fee_mode: Literal["free", "paid", "entitlement"]
    sessions: list[SessionItem] = Field(default_factory=list)
    instructors: list[InstructorItem] = Field(default_factory=list)
    review_summary: ReviewSummary
    remaining: int | None = Field(
        default=None,
        ge=0,
        description="当前用户权益余额（分）。仅 fee_mode=entitlement 时存在",
    )


class ErrorDetail(BaseModel):
    detail: str

