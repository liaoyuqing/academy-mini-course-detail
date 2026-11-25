"""报名资格状态枚举：与需求给定的 12 种取值逐字对应，不做任何改写。"""
from __future__ import annotations

from enum import Enum


class SignupState(str, Enum):
    CAN_SIGNUP = "can_signup"
    SIGNED_UP = "signed_up"
    WAITLISTED = "waitlisted"
    WAITLIST_AVAILABLE = "waitlist_available"
    PENDING_REVIEW = "pending_review"
    NEED_AUTH = "need_auth"
    NEED_MEMBER = "need_member"
    NO_ENTITLEMENT = "no_entitlement"
    NOT_OPEN = "not_open"
    CLOSED = "closed"
    FINISHED = "finished"
    APPLICATION = "application"


ALL_SIGNUP_STATES: tuple[str, ...] = tuple(item.value for item in SignupState)


def normalize_signup_state(raw: object) -> str | None:
    """把资格服务返回值收敛到 12 种枚举；未知值返回 None 由调用方降级。"""
    if raw is None:
        return None
    if not isinstance(raw, str):
        return None
    value = raw.strip().lower()
    try:
        return SignupState(value).value
    except ValueError:
        return None

