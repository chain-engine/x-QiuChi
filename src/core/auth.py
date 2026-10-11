"""
传输层认证模块（Bearer Token）

基于 mcp SDK 官方认证机制（``TokenVerifier`` Protocol）实现。
认证挂在 FastMCP 的 HTTP 传输层（``RequireAuthMiddleware``），
因此能读取到真实的 ``Authorization`` 请求头。

用法::

    from src.core.auth import SimpleTokenVerifier

    verifier = SimpleTokenVerifier(valid_tokens={"secret-token"})
    result = await verifier.verify_token("secret-token")  # -> AccessToken | None
"""

from __future__ import annotations

from typing import Any

from mcp.server.auth.provider import AccessToken

from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger(__name__)

__all__ = ["SimpleTokenVerifier", "AccessToken", "build_auth_from_settings"]


class SimpleTokenVerifier:
    """基于预设 token 集合的 Bearer Token 验证器。

    实现 mcp SDK 的 ``TokenVerifier`` Protocol（``verify_token`` 返回
    ``AccessToken | None``），适用于开发/测试与轻量内网部署场景。
    生产环境可替换为 JWT/OIDC 等真实验证器。
    """

    def __init__(
        self,
        valid_tokens: set[str] | None = None,
        client_id: str = "qiuchi",
    ) -> None:
        self.valid_tokens: set[str] = set(valid_tokens or [])
        self.client_id: str = client_id

    def add_token(self, token: str) -> None:
        """添加有效 token。"""
        self.valid_tokens.add(token)

    def remove_token(self, token: str) -> bool:
        """移除有效 token，返回是否成功。"""
        if token in self.valid_tokens:
            self.valid_tokens.remove(token)
            return True
        return False

    async def verify_token(self, token: str) -> AccessToken | None:
        """验证 Bearer token，有效则返回访问信息，否则返回 None。"""
        if token in self.valid_tokens:
            return AccessToken(
                token=token,
                client_id=self.client_id,
                scopes=[],
                expires_at=None,
            )
        return None


def build_auth_from_settings() -> tuple[Any | None, Any | None]:
    """从全局配置装配传输层认证（Bearer Token，走 mcp SDK 官方 RequireAuthMiddleware）。

    Returns:
        (auth_settings, token_verifier)；认证未启用时返回 (None, None)。
    """
    if not settings.middleware.auth.enabled:
        return None, None

    from mcp.server.auth.settings import AuthSettings
    from pydantic import AnyHttpUrl

    token_verifier = SimpleTokenVerifier(valid_tokens=set(settings.middleware.auth.tokens))
    if not token_verifier.valid_tokens:
        logger.warning(
            "Authentication enabled but no tokens configured (AUTH_TOKENS). "
            "All MCP requests will be rejected."
        )
    auth_settings = AuthSettings(
        issuer_url=AnyHttpUrl("https://qiuchi.local"),
        resource_server_url=AnyHttpUrl(f"http://{settings.mcp.host}:{settings.mcp.port}"),
    )
    return auth_settings, token_verifier
