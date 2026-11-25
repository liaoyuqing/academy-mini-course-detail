"""集中配置：全部从环境变量读取，仓库内不保存任何真实密钥。"""
from __future__ import annotations

import os
from dataclasses import dataclass


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _env_float(name: str, default: float) -> float:
    raw = _env(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    """运行期配置快照。每次读取环境变量现算，便于容器与测试注入。"""

    app_name: str
    app_env: str
    database_url: str
    redis_url: str
    crm_api_base: str
    crm_api_key: str
    crm_timeout_seconds: float
    enrollment_api_base: str
    enrollment_api_key: str
    enrollment_timeout_seconds: float
    mini_api_base: str
    mini_api_key: str
    log_level: str

    @property
    def use_mock_clients(self) -> bool:
        """本地演示与测试使用本地替身，不触达任何外部系统。"""
        return self.app_env.lower() in {"mock", "dev", "local"}


def load_settings() -> Settings:
    return Settings(
        app_name=_env("APP_NAME", "academy-mini-api"),
        app_env=_env("APP_ENV", "prod"),
        database_url=_env("DATABASE_URL", "sqlite+pysqlite:///./academy_demo.sqlite3"),
        redis_url=_env("REDIS_URL"),
        crm_api_base=_env("CRM_API_BASE"),
        crm_api_key=_env("CRM_API_KEY"),
        crm_timeout_seconds=_env_float("CRM_TIMEOUT_SECONDS", 2.0),
        enrollment_api_base=_env("ENROLLMENT_API_BASE"),
        enrollment_api_key=_env("ENROLLMENT_API_KEY"),
        enrollment_timeout_seconds=_env_float("ENROLLMENT_TIMEOUT_SECONDS", 1.5),
        mini_api_base=_env("MINI_API_BASE"),
        mini_api_key=_env("MINI_API_KEY"),
        log_level=_env("LOG_LEVEL", "INFO").upper(),
    )

