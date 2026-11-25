"""FastAPI 依赖：数据库会话、当前会员、CRM 与资格服务客户端。

每个依赖都可在测试里用 `app.dependency_overrides` 换成本地替身，
因此接口测试不触达任何外部系统，也不需要真实密钥。"""
from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from app.clients.crm_client import CrmClient
from app.clients.enrollment_check import EnrollmentCheckClient
from app.db.session import get_session_factory


def get_db() -> Iterator[Session]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def get_current_contact_id(
    request: Request,
    authorization: str | None = Header(default=None),
) -> str | None:
    """小程序登录态 -> 会员 contact_id；未登录返回 None（游客态）。"""
    client = request.app.state.mini_client
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if not token:
        token = request.headers.get("x-mini-token") or None
    return client.resolve_contact_id(token)


def get_crm_client(request: Request) -> CrmClient:
    return request.app.state.crm_client


def get_enrollment_client(request: Request) -> EnrollmentCheckClient:
    return request.app.state.enrollment_client


def get_db_session(db: Session = Depends(get_db)) -> Session:
    return db

