#!/usr/bin/env python3
"""
中间件模块

本模块提供 MCP 协议中间件支持（JSON-RPC 请求管道）：

    - ``Middleware`` / ``MiddlewareChain`` — 抽象基类与洋葱模型管道执行
    - ``RequestContext`` / ``ResponseContext`` — 请求/响应上下文数据类
    - ``ErrorHandlerMiddleware`` — MCP 请求错误处理（JSON-RPC 标准错误码）
    - ``LoggingMiddleware`` — MCP 请求/响应日志与性能告警
    - ``MCPAuthMiddleware`` / ``RoleBasedAuthMiddleware`` — MCP 认证与角色鉴权
    - ``CacheMiddleware`` — MCP 请求缓存（内存后端，可扩展）

Usage:
    from core.middleware import MiddlewareChain, ErrorHandlerMiddleware, LoggingMiddleware
    chain = MiddlewareChain()
    chain.add(ErrorHandlerMiddleware())
    chain.add(LoggingMiddleware())
"""

from __future__ import annotations

import hashlib
import inspect
import json
import time
import traceback
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple, TYPE_CHECKING

from core.logger import logger

if TYPE_CHECKING:
    from server.server import MCPServer

# ---------------------------------------------------------------------------
#  常量
# ---------------------------------------------------------------------------

# JSON-RPC 2.0 标准错误码
PARSE_ERROR: int = -32700
INVALID_REQUEST: int = -32600
METHOD_NOT_FOUND: int = -32601
INVALID_PARAMS: int = -32602
INTERNAL_ERROR: int = -32603

# 自定义错误码（-32000 ~ -32099）
AUTH_ERROR: int = -32001
PERMISSION_ERROR: int = -32002
RATE_LIMIT_ERROR: int = -32003

# MCP 认证中间件敏感字段集合
_SENSITIVE_FIELDS: frozenset[str] = frozenset(
    {
        "password", "token", "api_key", "secret", "auth",
        "credentials", "key", "passphrase", "private_key",
    }
)


# ═══════════════════════════════════════════════════════════════════════════
#  MCP 协议中间件（JSON-RPC 请求管道）
# ═══════════════════════════════════════════════════════════════════════════


# ---------------------------------------------------------------------------
#  基础抽象
# ---------------------------------------------------------------------------


@dataclass
class RequestContext:
    """MCP 请求上下文。

    封装 JSON-RPC 请求的完整信息，包括请求数据、关联服务器实例和元数据。

    Attributes:
        request: 原始 JSON-RPC 请求字典
        server: 关联的 MCPServer 实例（可选）
        metadata: 中间件间传递的元数据
    """

    request: Dict[str, Any]
    server: Optional["MCPServer"] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.metadata is None:
            self.metadata = {}

    @property
    def method(self) -> str:
        """JSON-RPC 方法名。"""
        return self.request.get("method", "")

    @property
    def request_id(self) -> str:
        """JSON-RPC 请求 ID。"""
        return self.request.get("id", "")


@dataclass
class ResponseContext:
    """MCP 响应上下文。

    Attributes:
        response: JSON-RPC 响应字典
        metadata: 中间件间传递的元数据
    """

    response: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.metadata is None:
            self.metadata = {}


Handler = Callable[[RequestContext], "ResponseContext"]
"""请求处理函数类型签名。"""


class Middleware(ABC):
    """MCP 中间件抽象基类。

    所有 MCP 协议中间件必须继承此类并实现 ``handle`` 方法。
    中间件通过 ``MiddlewareChain`` 组成洋葱模型管道执行。
    """

    @abstractmethod
    async def handle(
        self,
        request: RequestContext,
        next_handler: Handler,
    ) -> ResponseContext:
        """处理请求。

        Args:
            request: 当前 MCP 请求上下文
            next_handler: 下一个中间件或最终处理器

        Returns:
            MCP 响应上下文
        """
        ...

    async def __call__(
        self,
        request: RequestContext,
        next_handler: Handler,
    ) -> ResponseContext:
        return await self.handle(request, next_handler)


class MiddlewareChain:
    """MCP 中间件链。

    管理中间件的执行顺序，支持管道式处理。
    执行顺序：``chain[0] -> chain[1] -> ... -> chain[-1] -> final_handler``
    越靠前离调用者越近（洋葱模型的外层）。

    Example:
        chain = MiddlewareChain()
        chain.add(ErrorHandlerMiddleware())
        chain.add(LoggingMiddleware())
        chain.add(CacheMiddleware())
        response = await chain.execute(request, final_handler)
    """

    def __init__(self) -> None:
        self.middlewares: List[Middleware] = []
        self._names: List[str] = []

    def add(self, middleware: Middleware) -> "MiddlewareChain":
        """在链尾追加中间件。"""
        self.middlewares.append(middleware)
        self._names.append(type(middleware).__name__)
        return self

    def add_all(self, middlewares: List[Middleware]) -> "MiddlewareChain":
        """批量追加中间件。"""
        for m in middlewares:
            self.add(m)
        return self

    def insert(self, index: int, middleware: Middleware) -> "MiddlewareChain":
        """在指定位置插入中间件，支持负索引。"""
        if index < 0:
            index = max(0, len(self.middlewares) + index + 1)
        self.middlewares.insert(index, middleware)
        self._names.insert(index, type(middleware).__name__)
        return self

    def remove(self, middleware: Middleware) -> bool:
        """按实例移除中间件。"""
        try:
            idx = self.middlewares.index(middleware)
            self.middlewares.pop(idx)
            self._names.pop(idx)
            return True
        except ValueError:
            return False

    def remove_by_name(self, name: str) -> bool:
        """按类名移除中间件。"""
        for i, n in enumerate(list(self._names)):
            if n == name:
                self.middlewares.pop(i)
                self._names.pop(i)
                return True
        return False

    def clear(self) -> None:
        """清空所有中间件。"""
        self.middlewares.clear()
        self._names.clear()

    async def execute(
        self,
        request: RequestContext,
        final_handler: Handler,
    ) -> ResponseContext:
        """执行中间件链。

        从后往前 wrap：保证 ``self.middlewares[0]`` 是最外层。
        """
        handler = final_handler
        for middleware in reversed(self.middlewares):
            handler = self._wrap_handler(middleware, handler)
        return await handler(request)

    @staticmethod
    def _wrap_handler(
        middleware: Middleware,
        next_handler: Handler,
    ) -> Handler:
        async def wrapped_handler(request: RequestContext) -> ResponseContext:
            return await middleware(request, next_handler)
        return wrapped_handler

    def names(self) -> List[str]:
        """返回中间件名称列表（副本）。"""
        return list(self._names)

    def __len__(self) -> int:
        return len(self.middlewares)

    def __iter__(self):
        return iter(self.middlewares)

    def __contains__(self, name: str) -> bool:
        return name in self._names


# ---------------------------------------------------------------------------
#  错误处理
# ---------------------------------------------------------------------------


class ErrorHandlerMiddleware(Middleware):
    """MCP 错误处理中间件。

    捕获请求执行过程中的所有异常，返回符合 JSON-RPC 2.0 规范的错误响应。
    通常作为中间件链的最外层（第一个添加）。

    Args:
        include_traceback: 是否在错误响应中包含 traceback（生产环境建议关闭）
    """

    def __init__(self, include_traceback: bool = False) -> None:
        self.include_traceback = include_traceback

    async def handle(
        self,
        request: RequestContext,
        next_handler: Handler,
    ) -> ResponseContext:
        try:
            return await next_handler(request)
        except Exception as e:
            logger.error(f"Error processing request: {e}")
            if self.include_traceback:
                logger.error(traceback.format_exc())
            error_response = self._build_error_response(e, request)
            return ResponseContext(response=error_response)

    def _build_error_response(
        self,
        error: Exception,
        request: RequestContext,
    ) -> Dict[str, Any]:
        error_type = type(error).__name__
        error_message = str(error)

        error_response: Dict[str, Any] = {
            "jsonrpc": "2.0",
            "error": {
                "code": INTERNAL_ERROR,
                "message": f"Internal error: {error_type}",
                "data": {
                    "type": error_type,
                    "message": error_message,
                    "request_id": request.request.get("id"),
                },
            },
        }

        # JSON-RPC 规范要求响应带 id（即便发生错误）
        rid = request.request.get("id")
        if rid is not None:
            error_response["id"] = rid

        if self.include_traceback:
            error_response["error"]["data"]["traceback"] = traceback.format_exc()

        return error_response

    @staticmethod
    def create_validation_error(
        message: str,
        data: Optional[Dict[str, Any]] = None,
        rid: Any = None,
    ) -> Dict[str, Any]:
        """创建参数校验错误响应。"""
        resp: Dict[str, Any] = {
            "jsonrpc": "2.0",
            "error": {
                "code": INVALID_PARAMS,
                "message": f"Invalid params: {message}",
                "data": data or {},
            },
        }
        if rid is not None:
            resp["id"] = rid
        return resp

    @staticmethod
    def create_method_not_found_error(
        method: str,
        rid: Any = None,
    ) -> Dict[str, Any]:
        """创建方法未找到错误响应。"""
        resp: Dict[str, Any] = {
            "jsonrpc": "2.0",
            "error": {
                "code": METHOD_NOT_FOUND,
                "message": f"Method not found: {method}",
                "data": {"method": method},
            },
        }
        if rid is not None:
            resp["id"] = rid
        return resp


# ---------------------------------------------------------------------------
#  日志
# ---------------------------------------------------------------------------


class LoggingMiddleware(Middleware):
    """MCP 请求日志中间件。

    记录请求和响应的详细信息，支持敏感数据过滤和性能告警。

    Args:
        log_request: 是否记录请求日志
        log_response: 是否记录响应日志
        slow_threshold: 慢请求阈值（秒），超过此值输出 WARNING
    """

    def __init__(
        self,
        log_request: bool = True,
        log_response: bool = True,
        slow_threshold: Optional[float] = None,
    ) -> None:
        self.log_request = log_request
        self.log_response = log_response
        self.slow_threshold = slow_threshold

    async def handle(
        self,
        request: RequestContext,
        next_handler: Handler,
    ) -> ResponseContext:
        start_time = time.time()
        request_id = request.request.get("id", "unknown")
        method = request.request.get("method", "unknown")

        if self.log_request:
            self._log_request(request, request_id)

        try:
            response = await next_handler(request)
            execution_time = time.time() - start_time
            if self.log_response:
                self._log_response(response, request_id, execution_time, method)
            if self.slow_threshold is not None and execution_time > self.slow_threshold:
                logger.warning(
                    f"Performance warning: Request {request_id} ({method}) took "
                    f"{execution_time:.3f}s (threshold: {self.slow_threshold}s)"
                )
            return response
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                f"Request {request_id} failed after {execution_time:.3f}s: {e}"
            )
            raise

    def _log_request(self, request: RequestContext, request_id: str) -> None:
        request_data = request.request
        method = request_data.get("method", "unknown")
        params = request_data.get("params", {})
        filtered_params = self._filter_sensitive_data(params)
        source_location = self._get_source_location(method, request)

        log_message = f"Request {request_id}: method={method}"
        if source_location:
            log_message += f", location={source_location}"
        log_message += f", params={filtered_params}"
        logger.info(log_message)

    def _log_response(
        self,
        response: ResponseContext,
        request_id: str,
        execution_time: float,
        method: str,
    ) -> None:
        response_data = response.response
        if "error" in response_data:
            error_data = response_data.get("error", {})
            error_code = error_data.get("code", "unknown")
            error_message = error_data.get("message", "")
            logger.warning(
                f"Request {request_id} ({method}) failed after {execution_time:.3f}s: "
                f"code={error_code}, message={error_message}"
            )
        else:
            logger.info(
                f"Request {request_id} ({method}) completed in {execution_time:.3f}s"
            )

    @staticmethod
    def _filter_sensitive_data(data: Any) -> Any:
        """递归过滤敏感字段。"""
        if not isinstance(data, dict):
            return data
        filtered = data.copy()
        for field_name in _SENSITIVE_FIELDS:
            if field_name in filtered:
                filtered[field_name] = "***REDACTED***"
        for key, value in filtered.items():
            if isinstance(value, dict):
                filtered[key] = LoggingMiddleware._filter_sensitive_data(value)
            elif isinstance(value, list):
                filtered[key] = [
                    LoggingMiddleware._filter_sensitive_data(item)
                    if isinstance(item, dict) else item
                    for item in value
                ]
        return filtered

    def _get_source_location(
        self, method_name: str, request: RequestContext
    ) -> Optional[str]:
        """尝试获取处理函数的源码位置（用于调试）。"""
        server = getattr(request, "server", None)
        if not server or not hasattr(server, "registry"):
            return None
        try:
            from plugins.registry import RegistryItemType

            item = server.registry.get_item(method_name)
            if item and item.type == RegistryItemType.TOOL:
                return self._get_function_source(item.item)
        except Exception:
            return None
        return None

    @staticmethod
    def _get_function_source(func: Any) -> Optional[str]:
        """获取函数的源文件和行号。"""
        try:
            original = func
            while hasattr(original, "__wrapped__"):
                original = getattr(original, "__wrapped__")
            source_file = inspect.getsourcefile(original)
            if not source_file:
                return None
            import os
            import pathlib

            try:
                project_root = pathlib.Path(__file__).parent.parent.parent.resolve()
                rel_path = os.path.relpath(source_file, str(project_root))
            except Exception:
                rel_path = source_file
            _, lineno = inspect.getsourcelines(original)
            column = None
            try:
                lines, start_lineno = inspect.findsource(original)
                if lines:
                    func_line = lines[start_lineno]
                    def_pos = func_line.find("def ")
                    if def_pos != -1:
                        column = def_pos
            except Exception:
                pass
            if column is not None:
                return f"{rel_path}:{lineno}:{column}"
            return f"{rel_path}:{lineno}"
        except Exception:
            return None




# ---------------------------------------------------------------------------
#  认证
# ---------------------------------------------------------------------------


class AuthProvider(ABC):
    """MCP 认证提供者基类。

    子类需实现 ``authenticate`` 方法，接收请求数据返回认证信息。
    """

    @abstractmethod
    async def authenticate(
        self, request: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """认证请求。

        Args:
            request: 请求数据（含 headers / params）

        Returns:
            认证信息字典，认证失败返回 None
        """
        ...


class SimpleTokenAuthProvider(AuthProvider):
    """简单令牌认证提供者。

    基于预设的 token 集合进行认证，适用于开发和测试环境。

    Args:
        valid_tokens: 有效的 token 集合
    """

    def __init__(self, valid_tokens: Optional[Set[str]] = None) -> None:
        self.valid_tokens: Set[str] = set(valid_tokens or [])

    def add_token(self, token: str) -> None:
        """添加有效 token。"""
        self.valid_tokens.add(token)

    def remove_token(self, token: str) -> bool:
        """移除有效 token，返回是否成功。"""
        if token in self.valid_tokens:
            self.valid_tokens.remove(token)
            return True
        return False

    async def authenticate(
        self, request: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        headers = request.get("headers", {})
        params = request.get("params", {})

        # 兼容多种命名（大小写不敏感）
        auth_header = next(
            (v for k, v in headers.items() if str(k).lower() == "authorization"),
            "",
        )
        token = (
            auth_header.replace("Bearer ", "").strip() if auth_header else ""
        )
        if not token:
            token = (
                params.get("token")
                or params.get("api_key")
                or params.get("auth_token")
                or ""
            )

        if token and token in self.valid_tokens:
            return {
                "authenticated": True,
                "token": token,
                "user": "authenticated_user",
            }

        return None


class MCPAuthMiddleware(Middleware):
    """MCP 认证中间件。

    验证 MCP 请求的认证信息，支持多种认证提供者。
    用于 MCP 协议层的 JSON-RPC 请求认证。

    Args:
        auth_provider: 认证提供者实例
        required: 是否强制要求认证
        exempt_methods: 免认证的方法名列表
    """

    def __init__(
        self,
        auth_provider: Optional[AuthProvider] = None,
        required: bool = False,
        exempt_methods: Optional[List[str]] = None,
    ) -> None:
        self.auth_provider = auth_provider or SimpleTokenAuthProvider()
        self.required = required
        self.exempt_methods = set(exempt_methods or [])

        if (
            required
            and isinstance(self.auth_provider, SimpleTokenAuthProvider)
            and not self.auth_provider.valid_tokens
        ):
            logger.warning(
                "MCPAuthMiddleware configured with required=True but no valid tokens. "
                "All requests will be rejected."
            )

        logger.debug(f"MCPAuthMiddleware initialized (required={required})")

    def _extract_headers(self, request: RequestContext) -> Dict[str, Any]:
        """从请求中提取 headers（兼容 metadata 注入）。"""
        headers = request.request.get("headers", {}) or {}
        meta_headers = (
            request.metadata.get("headers", {})
            if hasattr(request, "metadata")
            else {}
        )
        return {**headers, **meta_headers}

    async def handle(
        self,
        request: RequestContext,
        next_handler: Handler,
    ) -> ResponseContext:
        method = request.request.get("method", "")
        if method in self.exempt_methods:
            logger.debug(f"Method {method} exempt from authentication")
            return await next_handler(request)

        auth_request = dict(request.request)
        auth_request["headers"] = self._extract_headers(request)
        auth_result = await self.auth_provider.authenticate(auth_request)

        if auth_result:
            request.metadata["auth"] = auth_result
            logger.debug(
                f"Request authenticated: {auth_result.get('user', 'unknown')}"
            )
            return await next_handler(request)
        elif self.required:
            logger.warning(f"Authentication failed for method: {method}")
            return self._create_auth_error_response()
        else:
            logger.debug(
                f"Authentication optional and failed for method: {method}"
            )
            return await next_handler(request)

    @staticmethod
    def _create_auth_error_response() -> ResponseContext:
        return ResponseContext(
            response={
                "jsonrpc": "2.0",
                "error": {
                    "code": AUTH_ERROR,
                    "message": "Authentication required",
                    "data": {
                        "type": "auth_error",
                        "message": "Valid authentication token is required",
                    },
                },
            }
        )

    def add_valid_token(self, token: str) -> None:
        """添加有效 token。"""
        if isinstance(self.auth_provider, SimpleTokenAuthProvider):
            self.auth_provider.add_token(token)
            logger.debug(f"Added valid token: {token[:8]}...")

    def remove_token(self, token: str) -> bool:
        """移除有效 token。"""
        if isinstance(self.auth_provider, SimpleTokenAuthProvider):
            ok = self.auth_provider.remove_token(token)
            if ok:
                logger.debug(f"Removed token: {token[:8]}...")
            return ok
        return False


# ---------------------------------------------------------------------------
#  缓存
# ---------------------------------------------------------------------------


class CacheBackend(ABC):
    """MCP 缓存后端基类。"""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值。"""
        ...

    @abstractmethod
    async def set(
        self, key: str, value: Any, ttl: Optional[int] = None
    ) -> bool:
        """设置缓存值。"""
        ...

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """删除缓存值。"""
        ...

    @abstractmethod
    async def clear(self) -> bool:
        """清空缓存。"""
        ...

    async def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息。"""
        return {"backend": type(self).__name__}


class MemoryCacheBackend(CacheBackend):
    """内存缓存后端（异步安全）。

    基于字典实现，支持 TTL 过期和容量上限保护。

    Args:
        max_size: 最大缓存条目数
    """

    def __init__(self, max_size: int = 1024) -> None:
        import asyncio

        self._cache: Dict[str, Tuple[Any, Optional[float]]] = {}
        self._lock = asyncio.Lock()
        self._max_size = max_size

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            value, expire_time = entry
            if expire_time is not None and time.time() > expire_time:
                self._cache.pop(key, None)
                return None
            return value

    async def set(
        self, key: str, value: Any, ttl: Optional[int] = None
    ) -> bool:
        async with self._lock:
            # 容量上限保护：避免无界增长
            if key not in self._cache and len(self._cache) >= self._max_size:
                victim = None
                for k, (_, exp) in self._cache.items():
                    if exp is None or time.time() > exp:
                        victim = k
                        break
                if victim is None:
                    victim = next(iter(self._cache))
                self._cache.pop(victim, None)
            expire_time = time.time() + ttl if ttl else None
            self._cache[key] = (value, expire_time)
            return True

    async def delete(self, key: str) -> bool:
        async with self._lock:
            return self._cache.pop(key, None) is not None

    async def clear(self) -> bool:
        async with self._lock:
            self._cache.clear()
            return True

    async def get_stats(self) -> Dict[str, Any]:
        async with self._lock:
            total = len(self._cache)
            now = time.time()
            expired = sum(
                1
                for _, (_, exp) in self._cache.items()
                if exp is not None and now > exp
            )
            return {
                "backend": "MemoryCacheBackend",
                "total_entries": total,
                "expired_entries": expired,
                "valid_entries": total - expired,
                "max_size": self._max_size,
            }


class CacheMiddleware(Middleware):
    """MCP 请求缓存中间件。

    缓存请求的响应结果，减少重复计算和外部调用。

    Args:
        cache_backend: 缓存后端实例，默认使用内存缓存
        default_ttl: 默认缓存过期时间（秒）
        enabled: 是否启用缓存
        cacheable_methods: 可缓存的方法名集合（空表示全部）
        bypass_header: 跳过缓存的请求头名称
    """

    def __init__(
        self,
        cache_backend: Optional[CacheBackend] = None,
        default_ttl: int = 300,
        enabled: bool = True,
        cacheable_methods: Optional[list] = None,
        bypass_header: str = "X-Cache-Bypass",
    ) -> None:
        self.cache_backend = cache_backend or MemoryCacheBackend()
        self.default_ttl = default_ttl
        self.enabled = enabled
        self.cacheable_methods = set(cacheable_methods or [])
        self.bypass_header = bypass_header

        logger.debug(
            f"CacheMiddleware initialized (enabled={enabled}, default_ttl={default_ttl}s)"
        )

    async def handle(
        self,
        request: RequestContext,
        next_handler: Handler,
    ) -> ResponseContext:
        if not self.enabled:
            return await next_handler(request)

        if self._should_bypass_cache(request):
            logger.debug(
                f"Bypassing cache for request: {request.request.get('id', 'unknown')}"
            )
            return await next_handler(request)

        method = request.request.get("method", "")
        if self.cacheable_methods and method not in self.cacheable_methods:
            return await next_handler(request)

        cache_key = self._generate_cache_key(request)

        cached_response = await self.cache_backend.get(cache_key)
        if cached_response is not None:
            logger.debug(f"Cache hit for key: {cache_key[:32]}...")
            request.metadata["cache_hit"] = True
            return ResponseContext(response=cached_response)

        logger.debug(f"Cache miss for key: {cache_key[:32]}...")
        response = await next_handler(request)

        if self._should_cache_response(response):
            ttl = self._get_ttl_for_request(request)
            await self.cache_backend.set(cache_key, response.response, ttl)
            logger.debug(
                f"Cached response for key: {cache_key[:32]}... (ttl={ttl}s)"
            )

        return response

    def _should_bypass_cache(self, request: RequestContext) -> bool:
        headers = request.request.get("headers", {})
        meta_headers = (
            request.metadata.get("headers", {})
            if hasattr(request, "metadata")
            else {}
        )
        bypass = headers.get(self.bypass_header, "") or meta_headers.get(
            self.bypass_header, ""
        )
        return str(bypass).lower() in ("true", "1", "yes")

    def _generate_cache_key(self, request: RequestContext) -> str:
        request_data = request.request
        method = request_data.get("method", "")
        params = request_data.get("params", {})
        headers = request_data.get("headers", {})

        cache_dict: Dict[str, Any] = {
            "method": method,
            "params": self._normalize_params(params),
        }

        auth_header = headers.get("Authorization")
        if auth_header:
            cache_dict["auth_hash"] = hashlib.sha256(
                auth_header.encode()
            ).hexdigest()

        cache_str = json.dumps(cache_dict, sort_keys=True, default=str)
        return f"qiuchi:cache:{hashlib.sha256(cache_str.encode()).hexdigest()}"

    @staticmethod
    def _normalize_params(params: Any) -> Any:
        if not isinstance(params, dict):
            return params
        normalized = {}
        for key, value in params.items():
            if isinstance(value, dict):
                normalized[key] = CacheMiddleware._normalize_params(value)
            elif isinstance(value, list):
                normalized[key] = [
                    CacheMiddleware._normalize_params(item)
                    if isinstance(item, dict)
                    else item
                    for item in value
                ]
            else:
                normalized[key] = value
        return normalized

    @staticmethod
    def _should_cache_response(response: ResponseContext) -> bool:
        return "error" not in response.response

    def _get_ttl_for_request(self, request: RequestContext) -> int:
        headers = request.request.get("headers", {})
        params = request.request.get("params", {})
        meta_headers = (
            request.metadata.get("headers", {})
            if hasattr(request, "metadata")
            else {}
        )

        ttl = (
            headers.get("X-Cache-TTL")
            or meta_headers.get("X-Cache-TTL")
            or params.get("cache_ttl")
            or self.default_ttl
        )
        try:
            return int(ttl)
        except (ValueError, TypeError):
            return self.default_ttl

    async def clear_cache(self) -> bool:
        """清空所有缓存。"""
        logger.info("Clearing cache...")
        return await self.cache_backend.clear()

    async def invalidate_method(self, method: str) -> int:
        """按方法名失效缓存（内存后端不支持模式匹配）。"""
        logger.warning(
            f"Memory cache does not support pattern invalidation for method: {method}"
        )
        return 0

    async def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息。"""
        return await self.cache_backend.get_stats()


# ═══════════════════════════════════════════════════════════════════════════
#  导出
# ═══════════════════════════════════════════════════════════════════════════

__all__ = [
    # --- MCP 协议中间件：基础 ---
    "RequestContext",
    "ResponseContext",
    "Handler",
    "Middleware",
    "MiddlewareChain",
    # --- MCP 协议中间件：功能 ---
    "ErrorHandlerMiddleware",
    "LoggingMiddleware",
    "enable_performance_logging",
    "MCPAuthMiddleware",
    "RoleBasedAuthMiddleware",
    "AuthProvider",
    "SimpleTokenAuthProvider",
    "CacheBackend",
    "MemoryCacheBackend",
    "CacheMiddleware",
    # --- 错误码常量 ---
    "PARSE_ERROR",
    "INVALID_REQUEST",
    "METHOD_NOT_FOUND",
    "INVALID_PARAMS",
    "INTERNAL_ERROR",
    "AUTH_ERROR",
    "PERMISSION_ERROR",
    "RATE_LIMIT_ERROR",
]
