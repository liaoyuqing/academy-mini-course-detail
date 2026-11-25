"""S2-CRM 对接点：只取企业能力卡四项公开摘要，联系方式在客户端层就被丢弃。

真实实现走 CRM_API_BASE + CRM_API_KEY（环境变量），本仓库默认用 MockCrmClient，
因此本单运行与测试不需要任何真实 CRM 后端与密钥。
"""
from __future__ import annotations

from typing import Protocol

import httpx

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger("crm")

PUBLIC_CARD_FIELDS = ("short_name", "industry", "ability_tags", "summary")


class CompanyCardPayload(dict):
    """CRM 返回的原始字典，可能夹带 contact/phone 等字段，由服务层再裁剪一次。"""


class CrmClient(Protocol):
    def fetch_company_card(self, crm_company_id: str) -> dict | None:
        """返回企业能力卡原始字典；企业不存在返回 None。"""


class MockCrmClient:
    """本地替身：按 crm_company_id 查内存字典，键为虚构企业编号。"""

    def __init__(self, cards: dict[str, dict] | None = None) -> None:
        self._cards = cards or {}

    def fetch_company_card(self, crm_company_id: str) -> dict | None:
        card = self._cards.get(crm_company_id)
        if card is None:
            return None
        return dict(card)


class HttpCrmClient:
    """内网 CRM 的 HTTP 实现；本单不联调，仅作为对接点保留。"""

    def __init__(self, settings: Settings) -> None:
        self._base = settings.crm_api_base.rstrip("/")
        self._key = settings.crm_api_key
        self._timeout = settings.crm_timeout_seconds

    def fetch_company_card(self, crm_company_id: str) -> dict | None:
        if not self._base:
            logger.warning("crm_not_configured company_id=%s", crm_company_id)
            return None
        url = f"{self._base}/companies/{crm_company_id}/capability-card"
        headers = {"X-Api-Key": self._key} if self._key else {}
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.get(url, headers=headers)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("crm_fetch_failed company_id=%s error=%s", crm_company_id, exc)
            return None
        if not isinstance(payload, dict):
            return None
        data = payload.get("data", payload)
        return data if isinstance(data, dict) else None


def build_crm_client(settings: Settings, cards: dict[str, dict] | None = None) -> CrmClient:
    if settings.use_mock_clients or not settings.crm_api_base:
        return MockCrmClient(cards)
    return HttpCrmClient(settings)

