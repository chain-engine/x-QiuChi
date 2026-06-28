"""
认证中间件

提供基础的认证和授权功能，支持多种认证方式。
"""

from typing import Any, Dict, List, Optional, Set
from abc import ABC, abstractmethod

from .base import Middleware, RequestContext, ResponseContext, Handler
from ..logging.logger import get_logger

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

    def __init__(self, valid_tokens: Set[str]):
        """
        初始化简单令牌认证

        Args:
            valid_tokens: 有效令牌集合
        """
        self.valid_tokens = valid_tokens

    async def authenticate(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """验证令牌"""
        # 从请求头或参数中提取令牌
        headers = request.get("headers", {})
        params = request.get("params", {})

        token = (
            headers.get("Authorization", "").replace("Bearer ", "") or
            params.get("token") or
            params.get("api_key")
        )

        if token in self.valid_tokens:
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
        required: bool = True,
        exempt_methods: Optional[List[str]] = None,
    ):
        """
        初始化认证中间件

        Args:
            auth_provider: 认证提供者（默认使用简单令牌认证）
            required: 是否必须认证
            exempt_methods: 免认证的方法列表
        """
        self.auth_provider = auth_provider or SimpleTokenAuthProvider(set())
        self.required = required
        self.exempt_methods = set(exempt_methods or [])

        logger.debug(f"AuthMiddleware initialized (required={required})")

    async def handle(
        self,
        request: RequestContext,
        next_handler: Handler,
    ) -> ResponseContext:
        """
        处理认证

        Args:
            request: 请求上下文
            next_handler: 下一个处理器

        Returns:
            响应上下文
        """
        # 检查是否免认证
        method = request.request.get("method", "")
        if method in self.exempt_methods:
            logger.debug(f"Method {method} exempt from authentication")
            return await next_handler(request)

        # 执行认证
        auth_result = await self.auth_provider.authenticate(request.request)

        if auth_result:
            # 认证成功，将认证信息添加到请求上下文
            request.metadata["auth"] = auth_result
            logger.debug(f"Request authenticated: {auth_result.get('user', 'unknown')}")
            return await next_handler(request)
        elif self.required:
            # 认证失败且必须认证
            logger.warning(f"Authentication failed for method: {method}")
            return self._create_auth_error_response()
        else:
            # 认证失败但不要求认证
            logger.debug(f"Authentication optional and failed for method: {method}")
            return await next_handler(request)

    def _create_auth_error_response(self) -> ResponseContext:
        """创建认证错误响应"""
        error_response = {
            "jsonrpc": "2.0",
            "error": {
                "code": -32001,  # 自定义认证错误代码
                "message": "Authentication required",
                "data": {
                    "type": "auth_error",
                    "message": "Valid authentication token is required"
                }
            }
        }
        return ResponseContext(response=error_response)

    def add_valid_token(self, token: str) -> None:
        """添加有效令牌（仅对 SimpleTokenAuthProvider 有效）"""
        if isinstance(self.auth_provider, SimpleTokenAuthProvider):
            self.auth_provider.valid_tokens.add(token)
            logger.debug(f"Added valid token: {token[:8]}...")

    def remove_token(self, token: str) -> bool:
        """移除令牌"""
        if isinstance(self.auth_provider, SimpleTokenAuthProvider):
            if token in self.auth_provider.valid_tokens:
                self.auth_provider.valid_tokens.remove(token)
                logger.debug(f"Removed token: {token[:8]}...")
                return True
        return False


class RoleBasedAuthMiddleware(AuthMiddleware):
    """基于角色的认证中间件"""

    def __init__(
        self,
        auth_provider: AuthProvider,
        role_mappings: Dict[str, List[str]],
        default_role: str = "guest",
    ):
        """
        初始化基于角色的认证中间件

        Args:
            auth_provider: 认证提供者
            role_mappings: 方法到所需角色的映射 {方法名: [所需角色]}
            default_role: 默认角色
        """
        super().__init__(auth_provider, required=True)
        self.role_mappings = role_mappings
        self.default_role = default_role

    async def handle(
        self,
        request: RequestContext,
        next_handler: Handler,
    ) -> ResponseContext:
        """处理基于角色的认证"""
        # 先执行基础认证
        response = await super().handle(request, next_handler)

        # 如果认证成功，检查角色权限
        if "auth" in request.metadata:
            method = request.request.get("method", "")
            user_roles = request.metadata["auth"].get("roles", [self.default_role])
            required_roles = self.role_mappings.get(method, [])

            # 检查用户是否有足够权限
            if required_roles and not any(role in user_roles for role in required_roles):
                logger.warning(
                    f"User with roles {user_roles} attempted to access "
                    f"method {method} requiring roles {required_roles}"
                )
                return self._create_permission_error_response()

        return response

    def _create_permission_error_response(self) -> ResponseContext:
        """创建权限错误响应"""
        error_response = {
            "jsonrpc": "2.0",
            "error": {
                "code": -32002,  # 自定义权限错误代码
                "message": "Permission denied",
                "data": {
                    "type": "permission_error",
                    "message": "Insufficient permissions to access this method"
                }
            }
        }
        return ResponseContext(response=error_response)