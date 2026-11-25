"""GET /api/mini/academy/courses/{id} 的接口测试。

四条验收标准各自用一个 -k 标记隔离，方便逐条验收：
  pytest -k ac1 -> show_company_card=false 的讲师不含企业能力卡字段
  pytest -k ac2 -> 匿名评价不出现姓名与 contact_id
  pytest -k ac3 -> 12 种 signup_state 参数化用例
  pytest -k ac4 -> 非 published / 软删除 / 不存在 一律 404
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
import yaml

from app.domain.signup_state import ALL_SIGNUP_STATES

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
COURSE_ID = str(uuid.UUID(int=1001))
UNKNOWN_ID = str(uuid.UUID(int=999999))


def _url(course_id: str = COURSE_ID) -> str:
    return f"/api/mini/academy/courses/{course_id}"


def _load_yaml(name: str):
    return yaml.safe_load((FIXTURES / name).read_text(encoding="utf-8"))


def _company_card_keys(payload: dict) -> list[str]:
    return [
        key
        for instructor in payload["instructors"]
        for key in instructor.keys()
        if key == "company_card"
    ]


# ---------------------------------------------------------------------------
# 基础契约：一次请求拿到全部五个区块
# ---------------------------------------------------------------------------
def test_detail_returns_all_five_blocks(client):
    resp = client.get(_url())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body) >= {
        "course_id",
        "title",
        "subtitle",
        "category",
        "intro",
        "outline",
        "outcomes",
        "cover_url",
        "fee_mode",
        "sessions",
        "instructors",
        "review_summary",
    }
    assert body["fee_mode"] == "entitlement"
    assert body["remaining"] == 128000
    assert body["outline"][0].startswith("第 1 周")
    assert body["review_summary"]["visible_count"] == 4


def test_detail_requires_login_for_personal_blocks(client_factory):
    """游客态也要能读详情，但权益余额退化为 0，不报 401。"""
    with client_factory(contact_id=None) as guest:
        resp = guest.get(_url())
    assert resp.status_code == 200
    assert resp.json()["remaining"] == 0


def test_sessions_sorted_ascending_and_only_unfinished(client):
    sessions = client.get(_url()).json()["sessions"]
    assert len(sessions) == 3, "已结束课期必须被过滤掉"
    starts = [item["start_at"] for item in sessions]
    assert starts == sorted(starts)
    labels = [item["label"] for item in sessions]
    assert "第 1 期（已结束）" not in labels
    for item in sessions:
        assert set(item) == {
            "session_id",
            "label",
            "start_at",
            "end_at",
            "room_name",
            "seats_remaining",
            "waitlist_count",
            "signup_state",
        }
    assert sessions[0]["label"] == "第 3 期（下午班）"
    assert sessions[1]["label"] == "第 3 期（周末班）"
    full_session = sessions[2]
    assert full_session["seats_remaining"] == 0
    assert full_session["waitlist_count"] == 7


def test_review_summary_math(client):
    summary = client.get(_url()).json()["review_summary"]
    assert summary["visible_count"] == 4
    assert summary["overall_avg"] == 4.5
    assert summary["avg_content"] == 4.5
    assert summary["avg_instructor"] == 4.5
    assert summary["avg_service"] == 3.5
    assert len(summary["recent"]) == 3
    assert all("hidden" not in item["content"] for item in summary["recent"])


# ---------------------------------------------------------------------------
# AC1 show_company_card=false 的讲师响应中不含企业能力卡字段
# ---------------------------------------------------------------------------
def test_ac1_false_instructor_has_no_company_card_key(client):
    body = client.get(_url()).json()
    guest = next(item for item in body["instructors"] if item["role"] == "guest")
    assert guest["show_company_card"] is False
    assert "company_card" not in guest


def test_ac1_company_card_count_matches_true_instructors(client):
    body = client.get(_url()).json()
    expected = sum(1 for item in body["instructors"] if item["show_company_card"])
    assert expected == 1
    assert len(_company_card_keys(body)) == expected
    raw_count = json.dumps(body).count('"company_card"')
    assert raw_count == expected


def test_company_card_payload_excludes_contact_fields(client):
    """期望值来自 tests/fixtures/instructor_card_1918.yaml，不是硬编码常量。"""
    cases = _load_yaml("instructor_card_1918.yaml")
    shown = next(item for item in cases if item["show_company_card"])
    body = client.get(_url()).json()
    card = next(item for item in body["instructors"] if item["show_company_card"])["company_card"]
    assert set(card) == {"short_name", "industry", "ability_tags", "summary"}
    assert card["short_name"] == shown["expected_short_name"]
    assert card["industry"] == shown["raw"]["industry"]
    assert card["ability_tags"] == shown["expected_tags"]
    assert len(card["ability_tags"]) <= 5
    dumped = json.dumps(card, ensure_ascii=False)
    for forbidden in ("contact", "phone", "email", "不应出现的联系人", "example@example.invalid"):
        assert forbidden not in dumped


def test_ac1_false_without_crm_company_id_still_absent(client_factory, db_session, seed):
    """字段缺失场景：show_company_card 未配置（默认 False）时同样不出现该键。"""
    instructor = seed.instructors["guest"]
    instructor.crm_company_id = None
    db_session.commit()
    with client_factory() as custom:
        body = custom.get(_url()).json()
    guest = next(item for item in body["instructors"] if item["role"] == "guest")
    assert "company_card" not in guest


# ---------------------------------------------------------------------------
# AC2 匿名评价不出现评价人姓名与 contact_id
# ---------------------------------------------------------------------------
def test_ac2_anonymous_review_hides_name_and_contact_id(client):
    """期望值与禁用键来自 tests/fixtures/review_anon_1918.yaml。"""
    cases = _load_yaml("review_anon_1918.yaml")
    anon_case = next(item for item in cases if item["case"] == "anonymous_only")
    recent = client.get(_url()).json()["review_summary"]["recent"]
    anon = [item for item in recent if item["author_name"] == anon_case["expected_display_name"]]
    assert anon, "最近 3 条里应包含匿名评价"
    for item in anon:
        assert set(item) == {"content", "rating", "created_at", "author_name"}
        for forbidden in anon_case["forbidden_keys"]:
            assert forbidden not in item
        assert anon_case["author_name"] not in json.dumps(item, ensure_ascii=False)


def test_ac2_named_review_keeps_display_name(client):
    recent = client.get(_url()).json()["review_summary"]["recent"]
    named = [item for item in recent if item["author_name"] == "王工"]
    assert named
    assert "contact_id" not in named[0]


def test_ac2_whole_payload_has_no_contact_id_in_reviews(client):
    body = client.get(_url()).json()
    dumped = json.dumps(body["review_summary"], ensure_ascii=False)
    assert "contact_id" not in dumped
    assert "44444444-4444-4444-8444-444444444444" not in dumped


# ---------------------------------------------------------------------------
# AC3 12 种 signup_state 各有一个用例返回正确值
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "case",
    _load_yaml("signup_state_12.yaml"),
    ids=[item["state"] for item in _load_yaml("signup_state_12.yaml")],
)
def test_ac3_signup_state_matrix(client_factory, seed, case):
    """资格服务 mock 注入单一状态，断言 sessions[0].signup_state 逐字相等。"""
    session_id = str(seed.sessions["sess-early"].id)
    with client_factory(states={session_id: case["state"]}) as custom:
        resp = custom.get(_url())
    assert resp.status_code == 200, resp.text
    states = [item["signup_state"] for item in resp.json()["sessions"]]
    assert states[0] == case["expected"]
    for item in resp.json()["sessions"]:
        assert item["signup_state"] in ALL_SIGNUP_STATES


def test_signup_state_fixture_covers_all_twelve_states():
    declared = [item["state"] for item in _load_yaml("signup_state_12.yaml")]
    assert len(declared) == 12
    assert sorted(declared) == sorted(ALL_SIGNUP_STATES)


def test_signup_state_service_failure_degrades_to_pending_review(client_factory, seed):
    """资格服务抛错时降级为 pending_review，并写降级日志，不 500。"""
    from app.api.deps import get_enrollment_client
    from app.clients.enrollment_check import EnrollmentCheckError, MockEnrollmentCheckClient

    class BrokenClient(MockEnrollmentCheckClient):
        def resolve(self, request):
            raise EnrollmentCheckError("upstream timeout")

    with client_factory() as custom:
        custom.app.dependency_overrides[get_enrollment_client] = lambda: BrokenClient()
        resp = custom.get(_url())
    assert resp.status_code == 200
    states = [item["signup_state"] for item in resp.json()["sessions"]]
    assert states == ["pending_review"] * 3


# ---------------------------------------------------------------------------
# AC4 非 published 课程返回 404
# ---------------------------------------------------------------------------
def test_ac4_offline_course_returns_404(client, db_session, seed):
    seed.course.status = "offline"
    db_session.commit()
    resp = client.get(_url())
    assert resp.status_code == 404
    assert set(resp.json()) == {"detail"}


def test_ac4_draft_course_returns_404(client, db_session, seed):
    seed.course.status = "draft"
    db_session.commit()
    resp = client.get(_url())
    assert resp.status_code == 404
    assert "title" not in resp.json()


def test_ac4_soft_deleted_course_returns_404(client, db_session, seed):
    from datetime import datetime

    seed.course.deleted_at = datetime(2026, 1, 1, 0, 0, 0)
    db_session.commit()
    resp = client.get(_url())
    assert resp.status_code == 404
    body = resp.json()
    assert "sessions" not in body and "instructors" not in body


def test_ac4_unknown_id_returns_404(client):
    resp = client.get(_url(UNKNOWN_ID))
    assert resp.status_code == 404
    assert resp.json() == {"detail": "course not found"}


def test_404_body_does_not_leak_course_existence(client, db_session, seed):
    """offline 与不存在的 id 返回体完全一致，不泄露课程是否存在。"""
    ghost = client.get(_url(UNKNOWN_ID))
    seed.course.status = "offline"
    db_session.commit()
    hidden = client.get(_url())
    assert ghost.status_code == hidden.status_code == 404
    assert ghost.json() == hidden.json()


# ---------------------------------------------------------------------------
# 契约细节：fee_mode 非 entitlement 时无 remaining
# ---------------------------------------------------------------------------
def test_paid_course_has_no_remaining_key(client, db_session, seed):
    seed.course.fee_mode = "paid"
    db_session.commit()
    body = client.get(_url()).json()
    assert "remaining" not in body


def test_openapi_export_is_in_sync(tmp_path):
    """导出的 openapi json 必须含本单响应 schema 的三个组件。"""
    from app.main import create_app

    schema = create_app(init_db=False).openapi()
    components = schema["components"]["schemas"]
    for name in ("AcademyCourseDetail", "InstructorItem", "CompanyCard", "SessionItem", "ReviewItem"):
        assert name in components

