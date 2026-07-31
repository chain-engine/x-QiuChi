"""
QiuChi 中间件系统

提供可扩展的中间件框架，支持：
- 请求/响应处理管道
- 错误处理
- 认证和授权
- 日志和监控
- 缓存
"""

from .base import Middleware, MiddlewareChain, RequestContext, ResponseContext, Handler
from .error_handler import (
    ErrorHandlerMiddleware,
    PARSE_ERROR,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    INVALID_PARAMS,
    INTERNAL_ERROR,
    AUTH_ERROR,
    PERMISSION_ERROR,
    RATE_LIMIT_ERROR,
)
from .logging import LoggingMiddleware, enable_performance_logging
from .auth import (
    AuthProvider,
    SimpleTokenAuthProvider,
    AuthMiddleware,
    RoleBasedAuthMiddleware,
)
from .cache import CacheBackend, MemoryCacheBackend, CacheMiddleware

__all__ = [
    "Middleware",
    "MiddlewareChain",
    "RequestContext",
    "ResponseContext",
    "Handler",
    "ErrorHandlerMiddleware",
    "PARSE_ERROR",
    "INVALID_REQUEST",
    "METHOD_NOT_FOUND",
    "INVALID_PARAMS",
    "INTERNAL_ERROR",
    "AUTH_ERROR",
    "PERMISSION_ERROR",
    "RATE_LIMIT_ERROR",
    "LoggingMiddleware",
    "enable_performance_logging",
    "AuthProvider",
    "SimpleTokenAuthProvider",
    "AuthMiddleware",
    "RoleBasedAuthMiddleware",
    "CacheBackend",
    "MemoryCacheBackend",
    "CacheMiddleware",
]
