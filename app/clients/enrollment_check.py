"""报名资格校验服务对接点。接口只负责透传 12 种 signup_state，
不在本服务内重新推导规则，避免与资格服务的判定分叉。

真实实现走 ENROLLMENT_API_BASE + ENROLLMENT_API_KEY（环境变量）；
本仓库默认 MockEnrollmentCheckClient，运行与测试均不需要真实服务。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.config import Settings
from app.core.logging import get_logger
from app.domain.signup_state import normalize_signup_state

logger = get_logger("enrollment")


class EnrollmentCheckError(RuntimeError):
    """资格服务不可用（超时、5xx、返回体不可解析）。"""


@dataclass(frozen=True)
class EnrollmentCheckRequest:
    course_id: str
    session_id: str
    contact_id: str | None
    capacity: int
    seats_taken: int
    waitlist_enabled: bool
    signup_mode: str
    session_status: str
    start_at: str
    end_at: str


class EnrollmentCheckClient(Protocol):
    def resolve(self, request: EnrollmentCheckRequest) -> str:
        """返回 12 种 signup_state 之一；服务不可用时抛 EnrollmentCheckError。"""


class MockEnrollmentCheckClient:
    """按 session_id 返回预设状态；未命中时按剩余名额给保守值。"""

    def __init__(self, states: dict[str, str] | None = None, default: str = "can_signup") -> None:
        self._states = states or {}
        self._default = default

    def resolve(self, request: EnrollmentCheckRequest) -> str:
        raw = self._states.get(request.session_id, self._default)
        state = normalize_signup_state(raw)
        if state is None:
            raise EnrollmentCheckError(f"unknown signup_state: {raw!r}")
        return state


class HttpEnrollmentCheckClient:
    """内网资格服务的 HTTP 实现；本单不联调，仅作为对接点保留。"""

    def __init__(self, settings: Settings) -> None:
        self._base = settings.enrollment_api_base.rstrip("/")
        self._key = settings.enrollment_api_key
        self._timeout = settings.enrollment_timeout_seconds

    def resolve(self, request: EnrollmentCheckRequest) -> str:
        if not self._base:
            raise EnrollmentCheckError("ENROLLMENT_API_BASE is not configured")
        headers = {"X-Api-Key": self._key} if self._key else {}
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(
                    f"{self._base}/signup-eligibility/resolve",
                    json=request.__dict__,
                    headers=headers,
                )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise EnrollmentCheckError(str(exc)) from exc
        raw = payload.get("signup_state") if isinstance(payload, dict) else None
        state = normalize_signup_state(raw)
        if state is None:
            raise EnrollmentCheckError(f"unknown signup_state: {raw!r}")
        return state


def build_enrollment_client(
    settings: Settings, states: dict[str, str] | None = None
) -> EnrollmentCheckClient:
    if settings.use_mock_clients or not settings.enrollment_api_base:
        return MockEnrollmentCheckClient(states)
    return HttpEnrollmentCheckClient(settings)

