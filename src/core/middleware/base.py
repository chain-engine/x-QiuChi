"""
QiuChi 中间件基类

定义中间件的标准接口和管道执行机制。
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional, TYPE_CHECKING
from dataclasses import dataclass

if TYPE_CHECKING:
    from ..server.server import MCPServer


@dataclass
class RequestContext:
    """请求上下文"""
    request: Dict[str, Any]
    server: "MCPServer"
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class ResponseContext:
    """响应上下文"""
    response: Dict[str, Any]
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


Handler = Callable[[RequestContext], ResponseContext]


class Middleware(ABC):
    """
    中间件基类

    所有中间件必须继承此类，实现 handle 方法。
    """

    @abstractmethod
    async def handle(
        self,
        request: RequestContext,
        next_handler: Handler,
    ) -> ResponseContext:
        """
        处理请求

        Args:
            request: 请求上下文
            next_handler: 下一个处理器

        Returns:
            响应上下文
        """
        pass

    async def __call__(
        self,
        request: RequestContext,
        next_handler: Handler,
    ) -> ResponseContext:
        """使中间件可调用"""
        return await self.handle(request, next_handler)


class MiddlewareChain:
    """
    中间件链

    管理中间件的执行顺序，支持管道式处理。
    """

    def __init__(self):
        self.middlewares: list[Middleware] = []

    def add(self, middleware: Middleware) -> "MiddlewareChain":
        """
        添加中间件

        Args:
            middleware: 中间件实例

        Returns:
            self (支持链式调用)
        """
        self.middlewares.append(middleware)
        return self

    def add_all(self, middlewares: list[Middleware]) -> "MiddlewareChain":
        """
        添加多个中间件

        Args:
            middlewares: 中间件列表

        Returns:
            self (支持链式调用)
        """
        self.middlewares.extend(middlewares)
        return self

    def insert(self, index: int, middleware: Middleware) -> "MiddlewareChain":
        """
        在指定位置插入中间件

        Args:
            index: 插入位置
            middleware: 中间件实例

        Returns:
            self (支持链式调用)
        """
        self.middlewares.insert(index, middleware)
        return self

    def remove(self, middleware: Middleware) -> bool:
        """
        移除中间件

        Args:
            middleware: 中间件实例

        Returns:
            是否移除成功
        """
        try:
            self.middlewares.remove(middleware)
            return True
        except ValueError:
            return False

    def clear(self) -> None:
        """清空中间件链"""
        self.middlewares.clear()

    async def execute(
        self,
        request: RequestContext,
        final_handler: Handler,
    ) -> ResponseContext:
        """
        执行中间件链

        Args:
            request: 请求上下文
            final_handler: 最终处理器（通常是业务逻辑）

        Returns:
            响应上下文
        """
        # 创建处理器链
        handler = final_handler
        for middleware in reversed(self.middlewares):
            handler = self._wrap_handler(middleware, handler)

        # 执行处理器链
        return await handler(request)

    def _wrap_handler(
        self,
        middleware: Middleware,
        next_handler: Handler,
    ) -> Handler:
        """包装中间件和处理器"""
        async def wrapped_handler(request: RequestContext) -> ResponseContext:
            return await middleware(request, next_handler)
        return wrapped_handler

    def __len__(self) -> int:
        """获取中间件数量"""
        return len(self.middlewares)

    def __iter__(self):
        """迭代中间件"""
        return iter(self.middlewares)