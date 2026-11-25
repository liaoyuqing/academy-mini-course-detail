"""统一时间口径：业务一律使用 UTC，落库与比较都用同一套 naive UTC。"""
from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """返回不带时区的 UTC 当前时间，避免 sqlite 与 PostgreSQL 行为分叉。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_iso_z(value: datetime | None) -> str | None:
    """序列化为带 Z 的 ISO8601，前端可直接 new Date() 解析。"""
    if value is None:
        return None
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed

