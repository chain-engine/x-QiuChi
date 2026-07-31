"""
认证中间件

提供基础的认证和授权功能，支持多种认证方式。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set
from abc import ABC, abstractmethod

from .base import Middleware, RequestContext, ResponseContext, Handler
from core.logging.logger import get_logger

logger = get_logger(__name__)


class AuthProvider(ABC):
    """认证提供者基类"""

    @abstractmethod
    async def authenticate(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        认证请求

        Args:
            request: 请求数据

        Returns:
            认证信息字典，认证失败返回 None
        """
        pass


class SimpleTokenAuthProvider(AuthProvider):
    """简单令牌认证提供者"""

    def __init__(self, valid_tokens: Optional[Set[str]] = None):
        self.valid_tokens: Set[str] = set(valid_tokens or [])

    def add_token(self, token: str) -> None:
        self.valid_tokens.add(token)

    def remove_token(self, token: str) -> bool:
        if token in self.valid_tokens:
            self.valid_tokens.remove(token)
            return True
        return False

    async def authenticate(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        headers = request.get("headers", {})
        params = request.get("params", {})

        # 兼容多种命名（大小写不敏感）
        auth_header = next(
            (v for k, v in headers.items() if str(k).lower() == "authorization"),
            "",
        )
        token = auth_header.replace("Bearer ", "").strip() if auth_header else ""
        if not token:
            token = params.get("token") or params.get("api_key") or params.get("auth_token") or ""

        if token and token in self.valid_tokens:
            return {"authenticated": True, "token": token, "user": "authenticated_user"}

        return None


class AuthMiddleware(Middleware):
    """
    认证中间件

    验证请求的认证信息，支持多种认证提供者。
    """

    def __init__(
        self,
        auth_provider: Optional[AuthProvider] = None,
        required: bool = False,
        exempt_methods: Optional[List[str]] = None,
    ):
        self.auth_provider = auth_provider or SimpleTokenAuthProvider()
        self.required = required
        self.exempt_methods = set(exempt_methods or [])

        if (
            required
            and isinstance(self.auth_provider, SimpleTokenAuthProvider)
            and not self.auth_provider.valid_tokens
        ):
            logger.warning(
                "AuthMiddleware configured with required=True but no valid tokens provided. "
                "All requests will be rejected."
            )

        logger.debug(f"AuthMiddleware initialized (required={required})")

    def _extract_headers(self, request: RequestContext) -> Dict[str, Any]:
        """从请求中提取 headers（兼容 metadata 注入）"""
        headers = request.request.get("headers", {}) or {}
        meta_headers = request.metadata.get("headers", {}) if hasattr(request, "metadata") else {}
        # 合并：meta_headers 优先（MCP 入口注入）
        merged = {**headers, **meta_headers}
        return merged

    async def handle(
        self,
        request: RequestContext,
        next_handler: Handler,
    ) -> ResponseContext:
        method = request.request.get("method", "")
        if method in self.exempt_methods:
            logger.debug(f"Method {method} exempt from authentication")
            return await next_handler(request)

        # 构造合并了 meta headers 的请求副本提供给 provider
        auth_request = dict(request.request)
        auth_request["headers"] = self._extract_headers(request)

        auth_result = await self.auth_provider.authenticate(auth_request)

        if auth_result:
            request.metadata["auth"] = auth_result
            logger.debug(f"Request authenticated: {auth_result.get('user', 'unknown')}")
            return await next_handler(request)
        elif self.required:
            logger.warning(f"Authentication failed for method: {method}")
            return self._create_auth_error_response()
        else:
            logger.debug(f"Authentication optional and failed for method: {method}")
            return await next_handler(request)

    def _create_auth_error_response(self) -> ResponseContext:
        error_response = {
            "jsonrpc": "2.0",
            "error": {
                "code": -32001,
                "message": "Authentication required",
                "data": {
                    "type": "auth_error",
                    "message": "Valid authentication token is required",
                },
            },
        }
        return ResponseContext(response=error_response)

    def add_valid_token(self, token: str) -> None:
        if isinstance(self.auth_provider, SimpleTokenAuthProvider):
            self.auth_provider.add_token(token)
            logger.debug(f"Added valid token: {token[:8]}...")

    def remove_token(self, token: str) -> bool:
        if isinstance(self.auth_provider, SimpleTokenAuthProvider):
            ok = self.auth_provider.remove_token(token)
            if ok:
                logger.debug(f"Removed token: {token[:8]}...")
            return ok
        return False


class RoleBasedAuthMiddleware(AuthMiddleware):
    """基于角色的认证中间件"""

    def __init__(
        self,
        auth_provider: AuthProvider,
        role_mappings: Dict[str, List[str]],
        default_role: str = "guest",
    ):
        super().__init__(auth_provider, required=True)
        self.role_mappings = role_mappings
        self.default_role = default_role

    async def handle(
        self,
        request: RequestContext,
        next_handler: Handler,
    ) -> ResponseContext:
        method = request.request.get("method", "")

        auth_request = dict(request.request)
        auth_request["headers"] = self._extract_headers(request)
        auth_result = await self.auth_provider.authenticate(auth_request)

        if auth_result:
            request.metadata["auth"] = auth_result
            user_roles = auth_result.get("roles", [self.default_role])
        else:
            user_roles = [self.default_role]

        required_roles = self.role_mappings.get(method, [])
        if required_roles and not any(role in user_roles for role in required_roles):
            logger.warning(
                f"User with roles {user_roles} attempted to access method {method} requiring roles {required_roles}"
            )
            return self._create_permission_error_response()

        return await next_handler(request)

    def _create_permission_error_response(self) -> ResponseContext:
        error_response = {
            "jsonrpc": "2.0",
            "error": {
                "code": -32002,
                "message": "Permission denied",
                "data": {
                    "type": "permission_error",
                    "message": "Insufficient permissions to access this method",
                },
            },
        }
        return ResponseContext(response=error_response)


__all__ = [
    "AuthProvider",
    "SimpleTokenAuthProvider",
    "AuthMiddleware",
    "RoleBasedAuthMiddleware",
]
