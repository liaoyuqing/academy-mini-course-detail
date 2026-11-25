"""FastAPI 应用入口。

运行：`uvicorn app.main:app --host 127.0.0.1 --port 8018`
接口：`GET /api/mini/academy/courses/{id}`、`GET /docs`、`GET /openapi.json`
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.mini.academy.courses_detail import router as academy_courses_router
from app.clients.crm_client import build_crm_client
from app.clients.demo_data import DEMO_CRM_CARDS, DEMO_MINI_TOKENS, DEMO_SIGNUP_STATES
from app.clients.enrollment_check import build_enrollment_client
from app.clients.mini_client import build_mini_client
from app.core.config import load_settings
from app.core.logging import get_logger
from app.db.session import create_all

logger = get_logger("main")


def create_app(
    database_url: str | None = None,
    init_db: bool = True,
) -> FastAPI:
    """应用工厂。测试传 init_db=False 并覆盖 get_db，避免动全局引擎。"""
    settings = load_settings()
    app = FastAPI(
        title="Academy Mini API",
        version="1.0.0",
        description="会员空间平台 · 学院 v1 小程序课程详情接口",
    )
    if init_db:
        create_all(database_url)
    app.state.settings = settings
    if settings.use_mock_clients:
        app.state.crm_client = build_crm_client(settings, DEMO_CRM_CARDS)
        app.state.enrollment_client = build_enrollment_client(settings, DEMO_SIGNUP_STATES)
        app.state.mini_client = build_mini_client(settings, DEMO_MINI_TOKENS)
    else:
        app.state.crm_client = build_crm_client(settings)
        app.state.enrollment_client = build_enrollment_client(settings)
        app.state.mini_client = build_mini_client(settings)
    app.include_router(academy_courses_router)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("unhandled_error path=%s", request.url.path)
        return JSONResponse(status_code=500, content={"detail": "internal server error"})

    return app


app = create_app()

