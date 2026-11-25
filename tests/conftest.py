"""测试装配：每个用例一套 sqlite 内存库 + 一套本地替身客户端，
不触达任何真实 CRM / 资格服务 / 小程序后端，也不需要任何密钥。"""
from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import (
    get_crm_client,
    get_current_contact_id,
    get_db,
    get_enrollment_client,
)
from app.clients.crm_client import MockCrmClient
from app.clients.enrollment_check import MockEnrollmentCheckClient
from app.clients.mini_client import MockMiniSessionClient
from app.db.base import Base
from app.db.models import (
    AcademyCourse,
    AcademyCourseInstructor,
    AcademyEntitlement,
    AcademyInstructor,
    AcademyReview,
    AcademySession,
)
from app.domain.clock import utc_now
from app.main import create_app

ORG_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
SITE_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")
CONTACT_ID = uuid.UUID("33333333-3333-4333-8333-333333333333")
ANOTHER_CONTACT_ID = uuid.UUID("44444444-4444-4444-8444-444444444444")

MINI_TOKEN = "dummy-mini-token-for-tests"


def fixed_uuid(value: int) -> uuid.UUID:
    return uuid.UUID(int=value)


class Seed:
    """测试数据的句柄：持有课程与课期 id，便于按用例断言。"""

    def __init__(self) -> None:
        self.course = None
        self.sessions = {}
        self.instructors = {}


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def crm_cards() -> dict:
    """虚构企业能力卡。原始数据故意夹带 contact 字段，用于验证客户端层裁剪。"""
    return {
        "crm-org-001": {
            "short_name": "云枢科技",
            "industry": "工业软件",
            "ability_tags": ["MES 实施", "产线数字化", "数据采集", "工艺建模", "培训交付", "溢出标签"],
            "summary": "为离散制造企业提供产线数字化改造与工艺建模服务。",
            "contact_name": "不应出现的联系人",
            "contact_phone": "000-0000-0000",
        },
        "crm-org-002": {
            "short_name": "衡远咨询",
            "industry": "管理咨询",
            "ability_tags": ["组织诊断", "薪酬体系"],
            "summary": "面向中型企业提供组织与人才体系咨询服务。",
            "contact_email": "example@example.invalid",
        },
    }


@pytest.fixture()
def seed(db_session) -> Seed:
    """一门 published 的 entitlement 课程：3 个未结束课期 + 1 个已结束课期，
    2 位讲师（一张卡 true 一张卡 false），4 条 visible 评价（含匿名）+ 1 条 hidden。"""
    handle = Seed()
    now = utc_now()
    course = AcademyCourse(
        id=fixed_uuid(1001),
        org_id=ORG_ID,
        site_id=SITE_ID,
        title="制造业产线数字化实战",
        subtitle="从设备联网到工艺闭环",
        category="manufacturing",
        intro="面向制造企业数字化负责人，六周完成一条产线的数据闭环。",
        outline=["第 1 周 设备联网与数据采集", "第 2 周 工艺参数建模"],
        outcomes=["能独立规划一条产线的采集点位", "能读懂 OEE 报表并定位损失"],
        cover_url="https://cdn.example.invalid/covers/manufacturing-101.png",
        fee_mode="entitlement",
        status="published",
        created_at=now - timedelta(days=30),
        updated_at=now - timedelta(days=1),
    )
    db_session.add(course)

    session_specs = [
        ("sess-early", "第 3 期（下午班）", now + timedelta(days=3), now + timedelta(days=3, hours=3), 30, 12, 2),
        ("sess-late", "第 4 期（晚班）", now + timedelta(days=10), now + timedelta(days=10, hours=3), 25, 25, 7),
        ("sess-mid", "第 3 期（周末班）", now + timedelta(days=6), now + timedelta(days=6, hours=3), 20, 5, 0),
        ("sess-closed", "第 1 期（已结束）", now - timedelta(days=20), now - timedelta(days=20, hours=-3), 30, 30, 0),
    ]
    for index, (key, label, start_at, end_at, capacity, taken, waitlist) in enumerate(session_specs):
        row = AcademySession(
            id=fixed_uuid(2001 + index),
            org_id=ORG_ID,
            site_id=SITE_ID,
            course_id=course.id,
            label=label,
            start_at=start_at,
            end_at=end_at,
            signup_open_at=start_at - timedelta(days=7),
            signup_deadline=start_at - timedelta(hours=1),
            room_name=f"A-{index + 1} 培训室",
            capacity=capacity,
            seats_taken=taken,
            waitlist_count=waitlist,
            waitlist_enabled=True,
            signup_mode="instant",
            status="scheduled" if end_at > now else "finished",
            created_at=now - timedelta(days=20),
            updated_at=now - timedelta(days=1),
        )
        db_session.add(row)
        handle.sessions[key] = row

    instructor_specs = [
        ("primary", "陈砚舟", "产线数字化顾问", "主导过 20 条产线的数据采集改造。", "instructor", True, "crm-org-001"),
        ("guest", "林知遥", "精益生产讲师", "十年精益改善与班组建设经验。", "guest", False, "crm-org-002"),
    ]
    for index, (key, name, headline, bio, role, show_card, company_id) in enumerate(instructor_specs):
        row = AcademyInstructor(
            id=fixed_uuid(3001 + index),
            org_id=ORG_ID,
            site_id=SITE_ID,
            display_name=name,
            headline=headline,
            bio=bio,
            avatar_url=f"https://cdn.example.invalid/avatars/{key}.png",
            role=role,
            show_company_card=show_card,
            crm_company_id=company_id,
            contact_id=None,
            created_at=now - timedelta(days=60),
            updated_at=now - timedelta(days=5),
        )
        db_session.add(row)
        db_session.add(
            AcademyCourseInstructor(
                id=fixed_uuid(3501 + index),
                org_id=ORG_ID,
                site_id=SITE_ID,
                course_id=course.id,
                instructor_id=row.id,
                sort_order=index,
                created_at=now - timedelta(days=60),
                updated_at=now - timedelta(days=5),
            )
        )
        handle.instructors[key] = row

    review_specs = [
        ("r1", True, True, 5, "课程节奏紧凑，采集点位那节课直接给了清单模板。", 1),
        ("r2", False, True, 4, "老师回答很细，晚班时间对上班族友好。", 2),
        ("r3", True, True, 5, "把自家产线的报表带过去，现场就改出来了。", 3),
        ("r4", False, True, 4, "希望多讲一些工艺侧的细节。", 4),
        ("r5", True, False, 1, "这条是 hidden，不应出现在摘要里。", 5),
    ]
    for index, (key, anonymous, visible, rating, content, days_ago) in enumerate(review_specs):
        db_session.add(
            AcademyReview(
                id=fixed_uuid(4001 + index),
                org_id=ORG_ID,
                site_id=SITE_ID,
                course_id=course.id,
                contact_id=ANOTHER_CONTACT_ID,
                author_name="王工" if not anonymous else "真实姓名不应泄露",
                anonymous=anonymous,
                visible=visible,
                content=content,
                rating=rating,
                rating_content=rating,
                rating_instructor=rating,
                rating_service=max(1, rating - 1),
                created_at=now - timedelta(days=days_ago),
                updated_at=now - timedelta(days=days_ago),
            )
        )

    db_session.add(
        AcademyEntitlement(
            id=fixed_uuid(5001),
            org_id=ORG_ID,
            site_id=SITE_ID,
            contact_id=CONTACT_ID,
            course_category="manufacturing",
            remaining_cents=128000,
            valid_until=now + timedelta(days=90),
            created_at=now - timedelta(days=10),
            updated_at=now - timedelta(days=10),
        )
    )
    db_session.commit()
    handle.course = course
    return handle


@pytest.fixture()
def enrollment_states() -> dict:
    return {}


@pytest.fixture()
def client(db_session, crm_cards, enrollment_states, seed):
    """默认装配：已登录会员 + 两张企业能力卡 + 资格服务默认 can_signup。"""
    app = create_app(init_db=False)

    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_contact_id] = lambda: str(CONTACT_ID)
    app.dependency_overrides[get_crm_client] = lambda: MockCrmClient(crm_cards)
    app.dependency_overrides[get_enrollment_client] = lambda: MockEnrollmentCheckClient(enrollment_states)
    app.state.mini_client = MockMiniSessionClient({MINI_TOKEN: str(CONTACT_ID)})
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def client_factory(db_session, crm_cards, seed):
    """可定制装配：按用例注入不同的资格状态表与登录态。"""

    def _build(
        states: dict | None = None,
        contact_id: str | None = str(CONTACT_ID),
        crm: MockCrmClient | None = None,
    ):
        app = create_app(init_db=False)
        states = states or {}

        def _override_db():
            yield db_session

        app.dependency_overrides[get_db] = _override_db
        app.dependency_overrides[get_current_contact_id] = lambda: contact_id
        app.dependency_overrides[get_crm_client] = lambda: crm or MockCrmClient(crm_cards)
        app.dependency_overrides[get_enrollment_client] = lambda: MockEnrollmentCheckClient(states)
        app.state.mini_client = MockMiniSessionClient({MINI_TOKEN: str(CONTACT_ID)})
        return TestClient(app)

    return _build

