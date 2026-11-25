"""跨库通用列类型：UUID 与 JSON 在 PostgreSQL 16 与 sqlite 上语义一致。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Uuid
from sqlalchemy.orm import mapped_column


def uuid_pk():
    """业务表统一主键：UUID，由应用层生成。"""
    return mapped_column(Uuid(as_uuid=True), primary_key=True)


def uuid_fk(nullable: bool = False, index: bool = True):
    return mapped_column(Uuid(as_uuid=True), nullable=nullable, index=index)


def utc_datetime(nullable: bool = False, index: bool = False):
    return mapped_column(DateTime(timezone=False), nullable=nullable, index=index)


def json_list():
    return mapped_column(JSON, nullable=False, default=list)


__all__ = [
    "datetime",
    "JSON",
    "uuid_pk",
    "uuid_fk",
    "utc_datetime",
    "json_list",
]
