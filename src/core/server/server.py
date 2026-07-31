"""
QiuChi 核心服务器类

企业级 MCP 服务器封装，提供插件化、中间件等高级特性。
"""

from __future__ import annotations

import asyncio
import inspect
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from mcp.server.fastmcp import FastMCP

from core.config.config import settings
from core.plugins import PluginManager
from core.transport.transport import TransportType
from core.server.lifecycle import LifecycleManager, ServerState
from plugins.collector import (
    register_server_collectors,
    unregister_server_collectors,
    set_active_server,
)
from core.middleware.base import (
    Middleware,
    MiddlewareChain,
    RequestContext,
    ResponseContext,
)
from core.middleware.error_handler import ErrorHandlerMiddleware
from core.middleware.logging import LoggingMiddleware
from core.middleware.auth import AuthMiddleware
from core.middleware.cache import CacheMiddleware
from core.logging.logger import get_logger

if TYPE_CHECKING:
    from core.transport.transport import TransportConfig

logger = get_logger(__name__)


class MCPServer:
    """
    企业级 MCP 服务器

    封装 FastMCP，提供：
    - 装饰器注册 Tools / Resources / Prompts
    - 中间件管道（ErrorHandler / Logging / Auth / Cache）
    - 插件自动发现与生命周期管理
    - 多传输层（Stdio / SSE / Streamable-HTTP）
    """

    def __init__(
        self,
        name: Optional[str] = None,
        version: Optional[str] = None,
        **kwargs: Any,
    ):
        self.name = name or settings.mcp.server_name
        self.version = version or settings.mcp.version

        # 创建底层 FastMCP 实例
        self.mcp = FastMCP(
            self.name,
            json_response=settings.mcp.json_response,
            host=settings.mcp.host,
            port=settings.mcp.port,
            **kwargs,
        )

        # 组件
        self.registry = _make_registry()  # 延迟创建以避免循环
        self.middleware_chain = MiddlewareChain()
        self.plugin_manager = PluginManager(self)
        self.lifecycle = LifecycleManager()

        # 注册当前 server 的隔离收集器
        register_server_collectors(self)

        # 注册默认中间件
        self._setup_default_middleware()

        # 状态
        self._startup_tasks: List[Callable] = []
        self._shutdown_tasks: List[Callable] = []

        # 记录已用中间件包装过的 FastMCP handler（防双重包装）
        self._wrapped_handlers: set = set()

        logger.info(f"MCP Server '{self.name}' v{self.version} initialized")

    # ------------------------------------------------------------------
    # 中间件设置
    # ------------------------------------------------------------------
    def _setup_default_middleware(self) -> None:
        # 错误处理（最外层）
        self.add_middleware(ErrorHandlerMiddleware(), index=0)

        # 日志
        if settings.features.middleware:
            self.add_middleware(LoggingMiddleware())

        # 认证
        if settings.middleware.auth.enabled:
            self.add_middleware(AuthMiddleware(
                required=settings.middleware.auth.required,
                exempt_methods=settings.middleware.auth.exempt_methods,
            ))

        # 缓存
        if settings.features.cache:
            self.add_middleware(CacheMiddleware())

        logger.debug(
            f"Setup {len(self.middleware_chain)} middlewares: {', '.join(self.middleware_chain.names())}"
        )

    def add_middleware(self, middleware: Middleware, index: Optional[int] = None) -> "MCPServer":
        if index is None:
            self.middleware_chain.add(middleware)
        else:
            self.middleware_chain.insert(index, middleware)
        logger.debug(f"Added middleware: {type(middleware).__name__}")
        return self

    def remove_middleware(self, middleware: Middleware) -> bool:
        return self.middleware_chain.remove(middleware)

    def remove_middleware_by_name(self, name: str) -> bool:
        return self.middleware_chain.remove_by_name(name)

    # ------------------------------------------------------------------
    # 插件管理
    # ------------------------------------------------------------------
    async def initialize_plugins(self) -> None:
        logger.info("Initializing plugin system...")

        # 装饰器收集的函数（轻量级插件）
        # 关键：在导入示例模块之前，激活当前 server，
        # 这样装饰器收集到的函数会进入 server 隔离的桶
        if settings.plugins.auto_discovery:
            import plugins.collector as collector_module
            logger.debug(f"Setting active server: {id(self)}")
            collector_module.set_active_server(self)
            try:
                # 先发现 Plugin 类（基于类的重型插件）
                self.plugin_manager.discover()
                # 再触发装饰器收集（lightweight plugins）
                self._discover_decorator_modules()
            finally:
                collector_module.set_active_server(None)

        # 加载所有 Plugin 类实例
        await self.plugin_manager.load_all()
        await self.plugin_manager.enable_all()

        # 注册到 registry + FastMCP
        self._register_decorator_functions()

    def _discover_decorator_modules(self) -> None:
        """触发装饰器收集

        关键：examples 模块可能在 create_server 之前就被 import（通过
        `from main import create_server` 间接触发），装饰器已经执行过一次。
        这里清除 sys.modules 中的缓存，强制重新 import。
        """
        import sys
        from plugins import discover_plugins

        # 清除 examples 模块缓存，强制重新 import 以触发装饰器
        modules_to_remove = [
            name for name in sys.modules
            if name.startswith("examples.")
        ]
        for name in modules_to_remove:
            sys.modules.pop(name, None)

        discover_plugins()

    def _should_register_func(self, name: str) -> bool:
        enabled = settings.plugins.enabled_plugins
        disabled = settings.plugins.disabled_plugins
        if disabled and name in disabled:
            return False
        if enabled and name not in enabled:
            return False
        return True

    def _register_decorator_functions(self) -> None:
        # 装饰器在模块 import 时收集。set_active_server(self) 已在
        # initialize_plugins 中调用过，所以使用 server 隔离的 collector。
        import plugins.collector as collector_module
        from plugins.base import PluginType

        bucket = collector_module._collectors_by_server.get(id(self), {})
        if bucket:
            tool_collector = bucket[PluginType.TOOL]
            resource_collector = bucket[PluginType.RESOURCE]
            prompt_collector = bucket[PluginType.PROMPT]
        else:
            # 兜底：使用全局
            tool_collector = collector_module._tool_collector
            resource_collector = collector_module._resource_collector
            prompt_collector = collector_module._prompt_collector

        for tool_name, info in tool_collector.get_items().items():
            if not self._should_register_func(tool_name):
                continue
            self._register_tool(tool_name, info)

        for resource_name, info in resource_collector.get_items().items():
            if not self._should_register_func(resource_name):
                continue
            self._register_resource(resource_name, info)

        for prompt_name, info in prompt_collector.get_items().items():
            if not self._should_register_func(prompt_name):
                continue
            self._register_prompt(prompt_name, info)

    def _build_middleware_wrapper(
        self,
        func: Callable,
        func_kind: str,
        func_id: str,
    ) -> Callable:
        """为 func 包裹中间件管道

        中间件在原函数执行前后插入。返回的 wrapper 既能被 MCP 直接调用
        （保持原签名），又能被外部代码通过 __wrapped__ 访问原函数。
        """
        from functools import wraps
        import inspect

        is_coro = inspect.iscoroutinefunction(func)

        @wraps(func)
        async def wrapped(*args, **kwargs):
            req = RequestContext(
                request={
                    "method": f"{func_kind}:{func_id}",
                    "id": str(id(wrapped)),
                    "params": kwargs,
                    "_args": args,
                    "_kwargs": kwargs,
                },
                server=self,
            )
            try:
                from runtime.context import get_current_context
                current = get_current_context()
                if current is not None:
                    req.metadata = dict(current.metadata)
            except Exception:
                pass

            async def _final_handler(req: RequestContext):
                try:
                    if is_coro:
                        result = await func(*req.request.get("_args", ()), **req.request.get("_kwargs", {}))
                    else:
                        result = func(*req.request.get("_args", ()), **req.request.get("_kwargs", {}))
                    if asyncio.iscoroutine(result):
                        result = await result
                    return ResponseContext(response={"result": result})
                except Exception:
                    raise

            response = await self.middleware_chain.execute(req, _final_handler)
            return response.response.get("result")

        # 保持可被外部识别为已包装函数
        wrapped.__wrapped__ = func
        return wrapped

    def _register_tool(self, name: str, info: Dict[str, Any]) -> None:
        from plugins import PluginMetadata
        wrapper = self._build_middleware_wrapper(info["func"], "tool", name)
        metadata = PluginMetadata(
            name=name,
            description=info["doc"],
            category=info["category"],
            subcategory=info["subcategory"],
            tags=info["tags"],
        )
        self.registry.register_tool(
            name=name,
            tool=wrapper,
            metadata=metadata,
            category=info["category"],
            subcategory=info["subcategory"],
            tags=info["tags"],
        )
        # FastMCP 1.x：直接传入原函数，让 FastMCP 自己分析 schema。
        # 由于 wrapper 不暴露给 FastMCP，中间件管道通过我们包装的入口触发。
        self.mcp.tool(name=name, description=info["doc"])(wrapper)
        logger.debug(f"Registered tool: {name}")

    def _register_resource(self, uri: str, info: Dict[str, Any]) -> None:
        from plugins import PluginMetadata
        wrapper = self._build_middleware_wrapper(info["func"], "resource", uri)
        metadata = PluginMetadata(
            name=uri,
            description=info["doc"],
            category=info["category"],
            subcategory=info["subcategory"],
            tags=info["tags"],
        )
        self.registry.register_resource(
            name=uri,
            resource=wrapper,
            metadata=metadata,
            category=info["category"],
            subcategory=info["subcategory"],
            tags=info["tags"],
        )
        self.mcp.resource(uri, name=uri, description=info["doc"])(wrapper)
        logger.debug(f"Registered resource: {uri}")

    def _register_prompt(self, name: str, info: Dict[str, Any]) -> None:
        from plugins import PluginMetadata
        wrapper = self._build_middleware_wrapper(info["func"], "prompt", name)
        metadata = PluginMetadata(
            name=name,
            description=info["doc"],
            category=info["category"],
            subcategory=info["subcategory"],
            tags=info["tags"],
        )
        self.registry.register_prompt(
            name=name,
            prompt=wrapper,
            metadata=metadata,
            category=info["category"],
            subcategory=info["subcategory"],
            tags=info["tags"],
        )
        self.mcp.prompt(name=name, description=info["doc"])(wrapper)
        logger.debug(f"Registered prompt: {name}")

    # ------------------------------------------------------------------
    # 便捷装饰器（@server.tool(...) 等价于 @tool(...)）
    # 这些走装饰器收集器流程，最终也会经过 _register_decorator_functions
    # ------------------------------------------------------------------
    def tool(self, name: Optional[str] = None, **metadata):
        from plugins import tool as tool_decorator
        return tool_decorator(name=name, **metadata)

    def resource(self, name: Optional[str] = None, **metadata):
        from plugins import resource as resource_decorator
        return resource_decorator(name=name, **metadata)

    def prompt(self, name: Optional[str] = None, **metadata):
        from plugins import prompt as prompt_decorator
        return prompt_decorator(name=name, **metadata)

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    async def start(self) -> None:
        if self.lifecycle.get_state() == ServerState.RUNNING:
            logger.warning("Server is already running")
            return

        logger.info(f"Starting MCP Server '{self.name}'...")
        await self.lifecycle.initialize()
        await self.lifecycle.startup()

        for task in self._startup_tasks:
            try:
                if inspect.iscoroutinefunction(task):
                    await task()
                else:
                    task()
            except Exception as e:
                logger.error(f"Startup task failed: {e}")

        await self.initialize_plugins()

        logger.info(f"MCP Server '{self.name}' started")

    async def stop(self) -> None:
        if not self.lifecycle.is_running():
            return

        logger.info(f"Stopping MCP Server '{self.name}'...")
        for task in self._shutdown_tasks:
            try:
                if inspect.iscoroutinefunction(task):
                    await task()
                else:
                    task()
            except Exception as e:
                logger.error(f"Shutdown task failed: {e}")

        await self.plugin_manager.shutdown()
        unregister_server_collectors(self)
        await self.lifecycle.shutdown()
        logger.info(f"MCP Server '{self.name}' stopped")

    def add_startup_task(self, task: Callable) -> "MCPServer":
        self._startup_tasks.append(task)
        return self

    def add_shutdown_task(self, task: Callable) -> "MCPServer":
        self._shutdown_tasks.append(task)
        return self

    # ------------------------------------------------------------------
    # 运行入口
    # ------------------------------------------------------------------
    def run(
        self,
        transport: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
    ) -> None:
        async def async_run():
            await self.start()
            from core.transport.transport import get_transport_config
            transport_config = get_transport_config(
                transport or settings.mcp.transport.value,
                host or settings.mcp.host,
                port or settings.mcp.port,
            )

            try:
                logger.info(f"Starting MCP Server with transport: {transport_config.transport.value}")
                if transport_config.transport == TransportType.STDIO:
                    await self.mcp.run_stdio_async()
                elif transport_config.transport == TransportType.SSE:
                    logger.info(f"Listening on {transport_config.host}:{transport_config.port}")
                    await self.mcp.run_sse_async()
                elif transport_config.transport == TransportType.STREAMABLE_HTTP:
                    logger.info(f"Listening on {transport_config.host}:{transport_config.port}")
                    await self.mcp.run_streamable_http_async()
                else:
                    raise ValueError(f"Unsupported transport type: {transport_config.transport.value}")
            except KeyboardInterrupt:
                logger.info("Server stopped by user")
            except Exception as e:
                logger.error(f"Server error: {e}")
                raise
            finally:
                await self.stop()

        try:
            asyncio.run(async_run())
        except KeyboardInterrupt:
            logger.info("Server shutdown complete")

    # ------------------------------------------------------------------
    # 查询接口
    # ------------------------------------------------------------------
    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": item.name,
                "description": item.metadata.description,
                "category": item.category,
                "subcategory": item.subcategory,
                "tags": list(item.tags),
            }
            for item in self.registry.get_all_items_by_str_type("tool")
        ]

    def get_resources(self) -> List[Dict[str, Any]]:
        return [
            {
                "uri": item.name,
                "description": item.metadata.description,
                "category": item.category,
                "subcategory": item.subcategory,
                "tags": list(item.tags),
            }
            for item in self.registry.get_all_items_by_str_type("resource")
        ]

    def get_prompts(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": item.name,
                "description": item.metadata.description,
                "category": item.category,
                "subcategory": item.subcategory,
                "tags": list(item.tags),
            }
            for item in self.registry.get_all_items_by_str_type("prompt")
        ]

    def get_stats(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "running": self.lifecycle.is_running(),
            "state": self.lifecycle.get_state().value,
            "tools": len(self.get_tools()),
            "resources": len(self.get_resources()),
            "prompts": len(self.get_prompts()),
            "middlewares": len(self.middleware_chain),
            "plugins": self.plugin_manager.stats(),
        }

    def context(self) -> "ContextManager":
        """获取上下文管理器（用于 with 语句）"""
        from runtime.context import ContextManager
        return ContextManager(self)

    def __repr__(self) -> str:
        return f"MCPServer(name='{self.name}', version='{self.version}', state={self.lifecycle.get_state().value})"


def create_server(
    name: Optional[str] = None,
    version: Optional[str] = None,
    **kwargs: Any,
) -> MCPServer:
    return MCPServer(name, version, **kwargs)


def _make_registry():
    """延迟创建 PluginRegistry 以避免循环导入"""
    from plugins.registry import PluginRegistry
    return PluginRegistry("ServerRegistry")
