"""
QiuChi 中间件基类

定义中间件的标准接口和管道执行机制。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING
from dataclasses import dataclass, field

if TYPE_CHECKING:
    from core.server.server import MCPServer


@dataclass
class RequestContext:
    """请求上下文"""
    request: Dict[str, Any]
    server: Optional["MCPServer"] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    @property
    def method(self) -> str:
        return self.request.get("method", "")

    @property
    def request_id(self) -> str:
        return self.request.get("id", "")


@dataclass
class ResponseContext:
    """响应上下文"""
    response: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


Handler = Callable[[RequestContext], "ResponseContext"]


class Middleware(ABC):
    """中间件抽象基类"""

    @abstractmethod
    async def handle(
        self,
        request: RequestContext,
        next_handler: Handler,
    ) -> ResponseContext:
        pass

    async def __call__(
        self,
        request: RequestContext,
        next_handler: Handler,
    ) -> ResponseContext:
        return await self.handle(request, next_handler)


class MiddlewareChain:
    """
    中间件链

    管理中间件的执行顺序，支持管道式处理。
    执行顺序：chain[0] -> chain[1] -> ... -> chain[-1] -> final_handler
    越靠前离调用者越近（洋葱模型的外层）。
    """

    def __init__(self):
        self.middlewares: List[Middleware] = []
        self._names: List[str] = []

    def add(self, middleware: Middleware) -> "MiddlewareChain":
        self.middlewares.append(middleware)
        self._names.append(type(middleware).__name__)
        return self

    def add_all(self, middlewares: List[Middleware]) -> "MiddlewareChain":
        for m in middlewares:
            self.add(m)
        return self

    def insert(self, index: int, middleware: Middleware) -> "MiddlewareChain":
        if index < 0:
            index = max(0, len(self.middlewares) + index + 1)
        self.middlewares.insert(index, middleware)
        self._names.insert(index, type(middleware).__name__)
        return self

    def remove(self, middleware: Middleware) -> bool:
        try:
            idx = self.middlewares.index(middleware)
            self.middlewares.pop(idx)
            self._names.pop(idx)
            return True
        except ValueError:
            return False

    def remove_by_name(self, name: str) -> bool:
        for i, n in enumerate(list(self._names)):
            if n == name:
                self.middlewares.pop(i)
                self._names.pop(i)
                return True
        return False

    def clear(self) -> None:
        self.middlewares.clear()
        self._names.clear()

    async def execute(
        self,
        request: RequestContext,
        final_handler: Handler,
    ) -> ResponseContext:
        # 从后往前 wrap：保证 self.middlewares[0] 是最外层
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
        return list(self._names)

    def __len__(self) -> int:
        return len(self.middlewares)

    def __iter__(self):
        return iter(self.middlewares)

    def __contains__(self, name: str) -> bool:
        return name in self._names


__all__ = ["RequestContext", "ResponseContext", "Handler", "Middleware", "MiddlewareChain"]
