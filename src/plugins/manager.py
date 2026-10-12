"""
插件管理器（插件子系统门面 / 编排者）

聚焦注册表体系：只做装饰器函数插件的发现与注册编排，
不承载扫描 / 收集 / 存储实现细节。

生命周期（装饰器插件：发现 → 收集 → 注册 → 调用）
--------------------------------------------------
① 发现（server.start() → initialize() → discover_plugins()）
   PluginDiscovery 扫描 discovery_paths
       │ import 子模块，触发装饰器收集
       ▼
   返回插件名单

② 收集（模块 import 时，装饰器副作用）
   业务代码: @tool / @resource / @prompt 标记函数
       │ 装饰器 collect() 自动写入（无需显式调用）
       ▼
   PluginCollector（全局单例，进程内唯一）

③ 注册（initialize() → _register_decorator_functions()）
   get_*_collector().get_items()
       ▼
   _register_item(item_type, name, info)
       ├─► _build_middleware_wrapper()：包裹中间件管道（注入 request_id）
       ├─► registry.register_<item_type>()：写入 ServerRegistry
       └─► mcp.<item_type>()(wrapper)：注册进 FastMCP

④ 调用（运行时）
   MCP 客户端 ──► FastMCP ──► wrapper（保持原签名）
       │ 构造 RequestContext（method / request_id / params）
       ▼
   middleware_chain.execute(req, final_handler)
       │ ErrorHandler → Logging → 原函数
       ▼
   返回结果

职责分工：发现委托 PluginDiscovery（临时创建、用后即弃）；
装饰器函数从全局 Collector 读取后注册到
server.registry（PluginRegistry）+ server.mcp（FastMCP）。
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from functools import wraps
from typing import Any

from src.core.config import settings
from src.core.logger import get_logger
from src.core.middleware import RequestContext, ResponseContext

from .registry import PluginMetadata

logger = get_logger(__name__)


class PluginManager:
    """
    插件管理器（插件子系统门面 / 编排者）

    只做编排与决策（发现顺序、注册分发），不承载扫描 / 收集 / 存储实现：
    - 发现：initialize() 内直接调 discover_plugins()
    - 注册：_register_decorator_functions() → _register_item()（registry + FastMCP）

    Args:
        server: MCPServer 实例（注册目标：server.registry / server.mcp / server.middleware_chain）
    """

    def __init__(self, server: Any):
        self.server = server

    # ------------------------------------------------------------------
    # 初始化：发现 → 注册
    # ------------------------------------------------------------------
    async def initialize(self) -> None:
        """初始化插件系统：发现插件 → 读取收集器 → 注册到 registry + FastMCP。"""
        logger.info("Initializing plugin system...")

        if not settings.plugins.auto_discovery:
            logger.warning("Plugin auto-discovery is disabled, no plugins will be loaded")
            return

        # 第一步：发现插件（过程中会触发装饰器收集）
        from .discovery import discover_plugins

        discover_plugins()

        # 第二步：注册插件（从收集器读取，统一注册）
        self._register_decorator_functions()

    def _register_decorator_functions(self) -> None:
        """从全局收集器读取装饰器函数，统一注册到 registry + FastMCP。"""
        from .collector import get_prompt_collector, get_resource_collector, get_tool_collector

        for tool_name, info in get_tool_collector().get_items().items():
            self._register_item("tool", tool_name, info)

        for resource_name, info in get_resource_collector().get_items().items():
            self._register_item("resource", resource_name, info)

        for prompt_name, info in get_prompt_collector().get_items().items():
            self._register_item("prompt", prompt_name, info)

    def _build_middleware_wrapper(
        self,
        func: Callable,
        func_type: str,
        func_id: str,
    ) -> Callable:
        """为 func 包裹中间件管道。

        中间件在原函数执行前后插入。返回的 wrapper 既能被 MCP 直接调用
        （保持原签名），又能被外部代码通过 __wrapped__ 访问原函数。
        """
        import inspect

        is_coro = inspect.iscoroutinefunction(func)

        @wraps(func)
        async def wrapped(*args, **kwargs):
            from src.transport.transport import get_request_id

            req = RequestContext(
                request={
                    "method": f"{func_type}:{func_id}",
                    "id": get_request_id(),  # 传输层注入的真实 request_id
                    "params": kwargs,
                    "_args": args,
                    "_kwargs": kwargs,
                },
                server=self.server,
            )

            async def _final_handler(req: RequestContext):
                if is_coro:
                    result = await func(
                        *req.request.get("_args", ()), **req.request.get("_kwargs", {})
                    )
                else:
                    result = func(*req.request.get("_args", ()), **req.request.get("_kwargs", {}))
                if asyncio.iscoroutine(result):
                    result = await result
                return ResponseContext(response={"result": result})

            response = await self.server.middleware_chain.execute(req, _final_handler)
            return response.response.get("result")

        # 保持可被外部识别为已包装函数
        wrapped.__wrapped__ = func
        return wrapped

    def _register_item(self, item_type: str, name: str, info: dict[str, Any]) -> None:
        """将单个装饰器收集项注册到 registry + FastMCP（tool/resource/prompt 统一入口）。

        Args:
            item_type: 插件类型，取值 "tool" / "resource" / "prompt"
            name: 工具名 / 资源 URI / 提示词名
            info: collector 收集项（含 func/doc/category/subcategory/tags）
        """

        # registry：按 item_type 分发到 register_tool / register_resource / register_prompt
        wrapper = self._build_middleware_wrapper(info["func"], item_type, name)
        metadata = PluginMetadata(
            name=name,
            description=info["doc"],
            category=info["category"],
            subcategory=info["subcategory"],
            tags=info["tags"],
        )
        register_fn = getattr(self.server.registry, f"register_{item_type}")
        register_fn(
            name=name,
            **{item_type: wrapper},
            metadata=metadata,
            category=info["category"],
            subcategory=info["subcategory"],
            tags=info["tags"],
        )

        # FastMCP：由 wrapper 承载中间件管道，schema 由 FastMCP 分析
        mcp_fn = getattr(self.server.mcp, item_type)
        if item_type == "resource":
            mcp_fn(name, name=name, description=info["doc"])(wrapper)
        else:
            mcp_fn(name=name, description=info["doc"])(wrapper)

        logger.debug(f"Registered {item_type}: {name}")


__all__ = ["PluginManager"]
