"""S3-MINI 对接点：把小程序会话 token 换成当前会员 contact_id。

真实实现应校验小程序登录态；本仓库提供本地替身，token 只来自环境变量映射，
不写入任何真实凭证。"""
from __future__ import annotations

from typing import Protocol

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger("mini")


class MiniSessionClient(Protocol):
    def resolve_contact_id(self, token: str | None) -> str | None:
        """token 无效或缺失返回 None（游客态）。"""


class MockMiniSessionClient:
    """token -> contact_id 的固定映射，仅测试与本地演示使用。"""

    def __init__(self, tokens: dict[str, str] | None = None) -> None:
        self._tokens = tokens or {}

    def resolve_contact_id(self, token: str | None) -> str | None:
        if not token:
            return None
        return self._tokens.get(token)


class EnvMiniSessionClient:
    """从 MINI_TOKEN_MAP（token=contact_id,token=contact_id）读取映射。"""

    def __init__(self, raw: str) -> None:
        self._tokens: dict[str, str] = {}
        for pair in raw.split(","):
            if "=" not in pair:
                continue
            token, contact_id = pair.split("=", 1)
            if token.strip() and contact_id.strip():
                self._tokens[token.strip()] = contact_id.strip()

    def resolve_contact_id(self, token: str | None) -> str | None:
        if not token:
            return None
        return self._tokens.get(token)


def build_mini_client(
    settings: Settings, tokens: dict[str, str] | None = None
) -> MiniSessionClient:
    if settings.use_mock_clients:
        return MockMiniSessionClient(tokens)
    return EnvMiniSessionClient(settings.mini_api_key)

