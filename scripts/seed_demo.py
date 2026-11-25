"""写入虚构演示数据：一门 published 课程 + 3 个未结束课期 + 2 位讲师 + 5 条评价。

用法：
  set DATABASE_URL=sqlite+pysqlite:///./demo.sqlite3
  python scripts/seed_demo.py

数据全部为虚构，不含任何真实个人或企业信息。"""
from __future__ import annotations

import sys
import uuid
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db.models import (  # noqa: E402
    AcademyCourse,
    AcademyCourseInstructor,
    AcademyEntitlement,
    AcademyInstructor,
    AcademyReview,
    AcademySession,
)
from app.db.session import create_all, get_session_factory  # noqa: E402
from app.domain.clock import utc_now  # noqa: E402

DEMO_COURSE_ID = uuid.UUID(int=1001)
ORG_ID = uuid.UUID(int=9001)
SITE_ID = uuid.UUID(int=9002)
CONTACT_ID = uuid.UUID(int=9003)


def seed() -> int:
    create_all()
    session = get_session_factory()()
    try:
        existing = session.get(AcademyCourse, DEMO_COURSE_ID)
        if existing is not None:
            print(f"demo course already present: {DEMO_COURSE_ID}")
            return 0
        now = utc_now()
        course = AcademyCourse(
            id=DEMO_COURSE_ID,
            org_id=ORG_ID,
            site_id=SITE_ID,
            title="制造业产线数字化实战",
            subtitle="从设备联网到工艺闭环",
            category="manufacturing",
            intro="面向制造企业数字化负责人，六周完成一条产线的数据闭环。",
            outline=["第 1 周 设备联网与数据采集", "第 2 周 工艺参数建模", "第 3 周 OEE 与损失分析"],
            outcomes=["能独立规划一条产线的采集点位", "能读懂 OEE 报表并定位损失"],
            cover_url="https://cdn.example.invalid/covers/manufacturing-101.png",
            fee_mode="entitlement",
            status="published",
            created_at=now - timedelta(days=30),
            updated_at=now - timedelta(days=1),
        )
        session.add(course)
        specs = [
            (100, "第 3 期（下午班）", 3, 30, 12, 2, "scheduled"),
            (101, "第 3 期（周末班）", 6, 20, 5, 0, "scheduled"),
            (102, "第 4 期（晚班）", 10, 25, 25, 7, "scheduled"),
            (103, "第 1 期（已结束）", -20, 30, 30, 0, "finished"),
        ]
        for offset, label, days, capacity, taken, waitlist, state in specs:
            start_at = now + timedelta(days=days)
            session.add(
                AcademySession(
                    id=uuid.UUID(int=2000 + offset),
                    org_id=ORG_ID,
                    site_id=SITE_ID,
                    course_id=course.id,
                    label=label,
                    start_at=start_at,
                    end_at=start_at + timedelta(hours=3),
                    signup_open_at=start_at - timedelta(days=7),
                    signup_deadline=start_at - timedelta(hours=1),
                    room_name=f"A-{offset - 99} 培训室",
                    capacity=capacity,
                    seats_taken=taken,
                    waitlist_count=waitlist,
                    waitlist_enabled=True,
                    signup_mode="instant",
                    status=state,
                    created_at=now - timedelta(days=20),
                    updated_at=now - timedelta(days=1),
                )
            )
        instructors = [
            (3001, "陈砚舟", "产线数字化顾问", "主导过 20 条产线的数据采集改造。", "instructor", True, "crm-org-001"),
            (3002, "林知遥", "精益生产讲师", "十年精益改善与班组建设经验。", "guest", False, "crm-org-002"),
        ]
        for index, (pid, name, headline, bio, role, show_card, company) in enumerate(instructors):
            row = AcademyInstructor(
                id=uuid.UUID(int=pid),
                org_id=ORG_ID,
                site_id=SITE_ID,
                display_name=name,
                headline=headline,
                bio=bio,
                avatar_url=f"https://cdn.example.invalid/avatars/{pid}.png",
                role=role,
                show_company_card=show_card,
                crm_company_id=company,
                contact_id=None,
                created_at=now - timedelta(days=60),
                updated_at=now - timedelta(days=5),
            )
            session.add(row)
            session.add(
                AcademyCourseInstructor(
                    id=uuid.UUID(int=3500 + index),
                    org_id=ORG_ID,
                    site_id=SITE_ID,
                    course_id=course.id,
                    instructor_id=row.id,
                    sort_order=index,
                    created_at=now - timedelta(days=60),
                    updated_at=now - timedelta(days=5),
                )
            )
        reviews = [
            (4001, True, True, 5, "课程节奏紧凑，采集点位那节课直接给了清单模板。", 1),
            (4002, False, True, 4, "老师回答很细，晚班时间对上班族友好。", 2),
            (4003, True, True, 5, "把自家产线的报表带过去，现场就改出来了。", 3),
            (4004, False, True, 4, "希望多讲一些工艺侧的细节。", 4),
            (4005, True, False, 1, "这条是 hidden，不应出现在摘要里。", 5),
        ]
        for rid, anonymous, visible, rating, content, days_ago in reviews:
            session.add(
                AcademyReview(
                    id=uuid.UUID(int=rid),
                    org_id=ORG_ID,
                    site_id=SITE_ID,
                    course_id=course.id,
                    contact_id=uuid.UUID(int=9100 + rid),
                    author_name="匿名学员" if anonymous else "王工",
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
        session.add(
            AcademyEntitlement(
                id=uuid.UUID(int=5001),
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
        # AC4 用的三门非可发布课程：offline / draft / 软删除，返回值一律 404。",
        for index, (status, deleted) in enumerate(
            [("offline", False), ("draft", False), ("published", True)], start=2
        ):
            session.add(
                AcademyCourse(
                    id=uuid.UUID(int=1000 + index),
                    org_id=ORG_ID,
                    site_id=SITE_ID,
                    title="非对外课程（用于 404 验收）",
                    subtitle=None,
                    category="manufacturing",
                    intro="该课程不对外展示，仅用于验收非 published 与软删除场景。",
                    outline=[],
                    outcomes=[],
                    cover_url=None,
                    fee_mode="free",
                    status=status,
                    created_at=now - timedelta(days=5),
                    updated_at=now - timedelta(days=5),
                    deleted_at=(now - timedelta(days=1)) if deleted else None,
                )
            )
        session.commit()
        print(f"seeded course {DEMO_COURSE_ID} with 4 sessions, 2 instructors, 5 reviews")
        print("seeded 3 non-published courses for 404 acceptance")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(seed())
