#!/usr/bin/env python3
"""
中间件模块

MCP 中间件体系：抽象基类、执行链与内置实现。

    - ``Middleware`` / ``MiddlewareChain`` — 抽象基类与洋葱模型执行链
    - ``RequestContext`` / ``ResponseContext`` — 中间件间传递的请求/响应信封
    - ``ErrorHandlerMiddleware`` — 错误处理中间件（JSON-RPC 标准错误码）
    - ``LoggingMiddleware`` — 请求/响应日志与性能告警中间件

Usage:
    from src.core.middleware import MiddlewareChain, ErrorHandlerMiddleware, LoggingMiddleware
    chain = MiddlewareChain()
    chain.add(ErrorHandlerMiddleware())
    chain.add(LoggingMiddleware())
"""

from __future__ import annotations

import inspect
import time
import traceback
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from src.core.logger import logger

if TYPE_CHECKING:
    from src.server.server import MCPServer

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
        "password",
        "token",
        "api_key",
        "secret",
        "auth",
        "credentials",
        "key",
        "passphrase",
        "private_key",
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

    request: dict[str, Any]
    server: MCPServer | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.metadata is None:
            self.metadata = {}

    @property
    def method(self) -> str:
        """JSON-RPC 方法名。"""
        return str(self.request.get("method", ""))

    @property
    def request_id(self) -> str:
        """JSON-RPC 请求 ID。"""
        return str(self.request.get("id", ""))


@dataclass
class ResponseContext:
    """MCP 响应上下文。

    Attributes:
        response: JSON-RPC 响应字典
        metadata: 中间件间传递的元数据
    """

    response: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.metadata is None:
            self.metadata = {}


Handler = Callable[[RequestContext], "Awaitable[ResponseContext]"]
"""请求处理函数类型签名（异步处理函数）。"""


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
    ) -> dict[str, Any]:
        error_type = type(error).__name__
        error_message = str(error)

        error_response: dict[str, Any] = {
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
        data: dict[str, Any] | None = None,
        rid: Any = None,
    ) -> dict[str, Any]:
        """创建参数校验错误响应。"""
        resp: dict[str, Any] = {
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
    ) -> dict[str, Any]:
        """创建方法未找到错误响应。"""
        resp: dict[str, Any] = {
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
        slow_threshold: float | None = None,
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
            logger.error(f"Request {request_id} failed after {execution_time:.3f}s: {e}")
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
            logger.info(f"Request {request_id} ({method}) completed in {execution_time:.3f}s")

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
                    if isinstance(item, dict)
                    else item
                    for item in value
                ]
        return filtered

    def _get_source_location(self, method_name: str, request: RequestContext) -> str | None:
        """尝试获取处理函数的源码位置（用于调试）。"""
        server = getattr(request, "server", None)
        if not server or not hasattr(server, "registry"):
            return None
        try:
            from src.constants import PluginType

            item = server.registry.get_item(method_name)
            if item and item.type == PluginType.TOOL:
                return self._get_function_source(item.item)
        except Exception:
            return None
        return None

    @staticmethod
    def _get_function_source(func: Any) -> str | None:
        """获取函数的源文件和行号。"""
        try:
            original = func
            while hasattr(original, "__wrapped__"):
                original = original.__wrapped__
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


class MiddlewareChain:
    """MCP 中间件链。

    管理中间件的执行顺序，支持管道式处理。
    执行顺序：``chain[0] -> chain[1] -> ... -> chain[-1] -> final_handler``
    越靠前离调用者越近（洋葱模型的外层）。

    Example:
        chain = MiddlewareChain()
        chain.add(ErrorHandlerMiddleware())
        chain.add(LoggingMiddleware())
        response = await chain.execute(request, final_handler)
    """

    def __init__(self) -> None:
        self.middlewares: list[Middleware] = []
        self._names: list[str] = []

    def add(self, middleware: Middleware) -> MiddlewareChain:
        """在链尾追加中间件。"""
        self.middlewares.append(middleware)
        self._names.append(type(middleware).__name__)
        return self

    def add_all(self, middlewares: list[Middleware]) -> MiddlewareChain:
        """批量追加中间件。"""
        for m in middlewares:
            self.add(m)
        return self

    def insert(self, index: int, middleware: Middleware) -> MiddlewareChain:
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

    def names(self) -> list[str]:
        """返回中间件名称列表（副本）。"""
        return list(self._names)

    def __len__(self) -> int:
        return len(self.middlewares)

    def __iter__(self):
        return iter(self.middlewares)

    def __contains__(self, name: str) -> bool:
        return name in self._names


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
