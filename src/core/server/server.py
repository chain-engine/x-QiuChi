"""
QiuChi 核心服务器类

企业级 MCP 服务器封装，提供插件化、中间件等高级特性。
"""

import asyncio
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING
from functools import wraps
import inspect

from mcp.server.fastmcp import FastMCP

from core.config.config import settings
from core.transport.transport import TransportType
from plugins.registry import PluginRegistry, RegistryItemType
from plugins import get_tool_collector, get_resource_collector, get_prompt_collector, PluginMetadata, discover_plugins
from core.middleware.base import MiddlewareChain, RequestContext, ResponseContext
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

    封装 FastMCP，提供插件化、中间件、统一错误处理等企业级特性。
    """

    def __init__(
        self,
        name: Optional[str] = None,
        version: Optional[str] = None,
        **kwargs,
    ):
        """
        初始化 MCP 服务器

        Args:
            name: 服务器名称（默认从配置读取）
            version: 服务器版本（默认从配置读取）
            **kwargs: 传递给 FastMCP 的其他参数
        """
        # 使用配置或参数
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

        # 初始化组件
        self.registry = PluginRegistry("ServerRegistry")
        self.middleware_chain = MiddlewareChain()

        # 默认中间件
        self._setup_default_middleware()

        # 状态
        self._is_running = False
        self._startup_tasks: List[Callable] = []
        self._shutdown_tasks: List[Callable] = []

        logger.info(f"MCP Server '{self.name}' v{self.version} initialized")

    def _setup_default_middleware(self) -> None:
        """设置默认中间件"""
        # 错误处理中间件（应该在最外层）
        self.middleware_chain.add(ErrorHandlerMiddleware())

        # 日志中间件
        if settings.features.middleware:
            self.middleware_chain.add(LoggingMiddleware())

        # 认证中间件（如果配置了认证）
        if settings.middleware.auth.enabled:
            self.middleware_chain.add(AuthMiddleware(
                required=settings.middleware.auth.required,
                exempt_methods=settings.middleware.auth.exempt_methods,
            ))

        # 缓存中间件
        if settings.features.cache:
            self.middleware_chain.add(CacheMiddleware())

        middleware_names = [type(m).__name__ for m in self.middleware_chain]
        logger.debug(f"Setup {len(self.middleware_chain)} default middlewares: {', '.join(middleware_names)}")

    # 插件管理
    async def initialize_plugins(self) -> None:
        """初始化插件系统（两阶段注册）"""
        logger.info("Initializing plugin system...")

        # 阶段1：发现插件（导入模块触发装饰器收集）
        if settings.plugins.auto_discovery:
            discovered = discover_plugins()
            logger.info(f"Discovered {len(discovered)} plugin items")

        # 阶段2：从收集器读取并注册所有装饰器标记的函数
        self._register_decorator_functions()

    def _register_decorator_functions(self) -> None:
        """注册装饰器标记的函数（从收集器读取）"""
        # 注册工具
        tool_collector = get_tool_collector()
        registered_tools = tool_collector.get_items()
        for tool_name, tool_info in registered_tools.items():
            wrapper = tool_info["func"]
            self.mcp.tool()(wrapper)
            metadata = PluginMetadata(
                name=tool_name,
                description=tool_info["doc"],
                category=tool_info["category"],
                subcategory=tool_info["subcategory"],
                tags=tool_info["tags"],
            )
            self.registry.register_tool(
                name=tool_name,
                tool=wrapper,
                metadata=metadata,
                category=tool_info["category"],
                subcategory=tool_info["subcategory"],
                tags=tool_info["tags"],
            )
            logger.debug(f"Registered decorator tool: {tool_name}")

        # 注册资源
        resource_collector = get_resource_collector()
        registered_resources = resource_collector.get_items()
        for resource_name, resource_info in registered_resources.items():
            wrapper = resource_info["func"]
            metadata = PluginMetadata(
                name=resource_name,
                description=resource_info["doc"],
                category=resource_info["category"],
                subcategory=resource_info["subcategory"],
                tags=resource_info["tags"],
            )
            self.registry.register_resource(
                name=resource_name,
                resource=wrapper,
                metadata=metadata,
                category=resource_info["category"],
                subcategory=resource_info["subcategory"],
                tags=resource_info["tags"],
            )
            logger.debug(f"Registered decorator resource: {resource_name}")

        # 注册提示词
        prompt_collector = get_prompt_collector()
        registered_prompts = prompt_collector.get_items()
        for prompt_name, prompt_info in registered_prompts.items():
            wrapper = prompt_info["func"]
            metadata = PluginMetadata(
                name=prompt_name,
                description=prompt_info["doc"],
                category=prompt_info["category"],
                subcategory=prompt_info["subcategory"],
                tags=prompt_info["tags"],
            )
            self.registry.register_prompt(
                name=prompt_name,
                prompt=wrapper,
                metadata=metadata,
                category=prompt_info["category"],
                subcategory=prompt_info["subcategory"],
                tags=prompt_info["tags"],
            )
            logger.debug(f"Registered decorator prompt: {prompt_name}")

        total_count = len(registered_tools) + len(registered_resources) + len(registered_prompts)
        if total_count > 0:
            logger.info(f"Registered {total_count} decorator functions: {len(registered_tools)} tools, {len(registered_resources)} resources, {len(registered_prompts)} prompts")

    # 中间件管理
    def add_middleware(self, middleware: Any, index: Optional[int] = None) -> "MCPServer":
        """
        添加中间件

        Args:
            middleware: 中间件实例
            index: 插入位置（None 表示追加到末尾）

        Returns:
            self (支持链式调用)
        """
        from core.middleware.base import Middleware
        if isinstance(middleware, Middleware):
            if index is None:
                self.middleware_chain.add(middleware)
            else:
                self.middleware_chain.insert(index, middleware)
            source_file = inspect.getfile(middleware.__class__)
            logger.debug(f"Added middleware: {type(middleware).__name__} from {source_file}")
        return self

    def remove_middleware(self, middleware: Any) -> bool:
        """
        移除中间件

        Args:
            middleware: 中间件实例

        Returns:
            是否移除成功
        """
        from core.middleware.base import Middleware
        if isinstance(middleware, Middleware):
            return self.middleware_chain.remove(middleware)
        return False

    # 工具注册（兼容新旧 API）
    def tool(self, func: Optional[Callable] = None, **metadata):
        """
        注册工具装饰器

        Args:
            func: 工具函数
            **metadata: 元数据

        Returns:
            装饰器或装饰后的函数
        """
        def decorator(f: Callable) -> Callable:
            @wraps(f)
            async def wrapper(*args, **kwargs):
                request_context = RequestContext(
                    request={"method": f.__name__, "params": kwargs},
                    server=self,
                )

                async def final_handler(req: RequestContext) -> ResponseContext:
                    try:
                        result = await f(*args, **kwargs) if inspect.iscoroutinefunction(f) else f(*args, **kwargs)
                        return ResponseContext(response={"result": result})
                    except Exception as e:
                        raise

                response = await self.middleware_chain.execute(request_context, final_handler)
                return response.response.get("result")

            plugin_metadata = PluginMetadata(
                name=metadata.get("name", f.__name__),
                description=metadata.get("description", f.__doc__ or ""),
                category=metadata.get("category", "default"),
                subcategory=metadata.get("subcategory"),
                tags=metadata.get("tags", []),
            )

            self.registry.register_tool(
                name=metadata.get("name", f.__name__),
                tool=wrapper,
                metadata=plugin_metadata,
                category=metadata.get("category", "default"),
                subcategory=metadata.get("subcategory"),
                tags=metadata.get("tags", []),
            )

            self.mcp.tool()(wrapper)

            source_info = self._get_function_source_info(f)
            tool_name = metadata.get("name", f.__name__)
            if source_info:
                logger.info(f"Registered tool '{tool_name}' at {source_info}")
            else:
                logger.info(f"Registered tool '{tool_name}'")

            return wrapper

        if func is None:
            return decorator
        return decorator(func)

    def resource(self, uri: str, **metadata):
        """
        注册资源装饰器

        Args:
            uri: 资源 URI
            **metadata: 元数据

        Returns:
            装饰器
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(*args, **kwargs):
                request_context = RequestContext(
                    request={"method": f"resource:{uri}", "params": kwargs},
                    server=self,
                )

                async def final_handler(req: RequestContext) -> ResponseContext:
                    result = await func(*args, **kwargs) if inspect.iscoroutinefunction(func) else func(*args, **kwargs)
                    return ResponseContext(response={"result": result})

                response = await self.middleware_chain.execute(request_context, final_handler)
                return response.response.get("result")

            plugin_metadata = PluginMetadata(
                name=uri,
                description=metadata.get("description", func.__doc__ or ""),
                category=metadata.get("category", "default"),
                subcategory=metadata.get("subcategory"),
                tags=metadata.get("tags", []),
            )

            self.registry.register_resource(
                name=uri,
                resource=wrapper,
                metadata=plugin_metadata,
                category=metadata.get("category", "default"),
                subcategory=metadata.get("subcategory"),
                tags=metadata.get("tags", []),
            )

            self.mcp.resource(uri)(wrapper)

            source_info = self._get_function_source_info(func)
            if source_info:
                logger.info(f"Registered resource '{uri}' at {source_info}")
            else:
                logger.info(f"Registered resource '{uri}'")

            return wrapper

        return decorator

    def prompt(self, name: str, **metadata):
        """
        注册提示词装饰器

        Args:
            name: 提示词名称
            **metadata: 元数据

        Returns:
            装饰器
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(*args, **kwargs):
                request_context = RequestContext(
                    request={"method": f"prompt:{name}", "params": kwargs},
                    server=self,
                )

                async def final_handler(req: RequestContext) -> ResponseContext:
                    result = await func(*args, **kwargs) if inspect.iscoroutinefunction(func) else func(*args, **kwargs)
                    return ResponseContext(response={"result": result})

                response = await self.middleware_chain.execute(request_context, final_handler)
                return response.response.get("result")

            plugin_metadata = PluginMetadata(
                name=name,
                description=metadata.get("description", func.__doc__ or ""),
                category=metadata.get("category", "default"),
                subcategory=metadata.get("subcategory"),
                tags=metadata.get("tags", []),
            )

            self.registry.register_prompt(
                name=name,
                prompt=wrapper,
                metadata=plugin_metadata,
                category=metadata.get("category", "default"),
                subcategory=metadata.get("subcategory"),
                tags=metadata.get("tags", []),
            )

            self.mcp.prompt()(wrapper)

            source_info = self._get_function_source_info(func)
            if source_info:
                logger.info(f"Registered prompt '{name}' at {source_info}")
            else:
                logger.info(f"Registered prompt '{name}'")

            return wrapper

        return decorator

    # 服务器生命周期
    async def start(self) -> None:
        """启动服务器"""
        if self._is_running:
            logger.warning("Server is already running")
            return

        logger.info(f"Starting MCP Server '{self.name}'...")

        # 执行启动任务
        for task in self._startup_tasks:
            try:
                if inspect.iscoroutinefunction(task):
                    await task()
                else:
                    task()
            except Exception as e:
                logger.error(f"Startup task failed: {e}")

        # 初始化插件
        await self.initialize_plugins()

        self._is_running = True
        logger.info(f"MCP Server '{self.name}' started")

    async def stop(self) -> None:
        """停止服务器"""
        if not self._is_running:
            return

        logger.info(f"Stopping MCP Server '{self.name}'...")

        # 执行关闭任务
        for task in self._shutdown_tasks:
            try:
                if inspect.iscoroutinefunction(task):
                    await task()
                else:
                    task()
            except Exception as e:
                logger.error(f"Shutdown task failed: {e}")

        self._is_running = False
        logger.info(f"MCP Server '{self.name}' stopped")

    def add_startup_task(self, task: Callable) -> "MCPServer":
        """
        添加启动任务

        Args:
            task: 启动任务函数（可以是异步函数）

        Returns:
            self (支持链式调用)
        """
        self._startup_tasks.append(task)
        return self

    def add_shutdown_task(self, task: Callable) -> "MCPServer":
        """
        添加关闭任务

        Args:
            task: 关闭任务函数（可以是异步函数）

        Returns:
            self (支持链式调用)
        """
        self._shutdown_tasks.append(task)
        return self

    # 服务器运行
    def run(
        self,
        transport: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
    ) -> None:
        """
        运行服务器

        Args:
            transport: 传输类型 (stdio, sse, streamable-http)
            host: HTTP 监听地址
            port: HTTP 监听端口
        """
        import asyncio

        # 运行异步启动
        async def async_run():
            await self.start()

            # 获取传输配置
            from core.transport.transport import get_transport_config
            transport_config = get_transport_config(
                transport or settings.mcp.transport.value,
                host or settings.mcp.host,
                port or settings.mcp.port,
            )

            # 运行 FastMCP
            try:
                logger.info(f"Starting MCP Server with transport: {transport_config.transport.value}")

                # 根据传输类型调用对应的 FastMCP 方法
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

        # 运行事件循环
        try:
            asyncio.run(async_run())
        except KeyboardInterrupt:
            logger.info("Server shutdown complete")

    # 查询接口
    def get_tools(self) -> List[Dict[str, Any]]:
        """获取所有工具"""
        tools = []
        for item in self.registry.get_all_items(item_type=RegistryItemType.TOOL):
            tools.append({
                "name": item.name,
                "description": item.metadata.description,
                "category": item.category,
                "subcategory": item.subcategory,
                "tags": list(item.tags),
            })
        return tools

    def get_resources(self) -> List[Dict[str, Any]]:
        """获取所有资源"""
        resources = []
        for item in self.registry.get_all_items(item_type=RegistryItemType.RESOURCE):
            resources.append({
                "uri": item.name,
                "description": item.metadata.description,
                "category": item.category,
                "subcategory": item.subcategory,
                "tags": list(item.tags),
            })
        return resources

    def get_prompts(self) -> List[Dict[str, Any]]:
        """获取所有提示词"""
        prompts = []
        for item in self.registry.get_all_items(item_type=RegistryItemType.PROMPT):
            prompts.append({
                "name": item.name,
                "description": item.metadata.description,
                "category": item.category,
                "subcategory": item.subcategory,
                "tags": list(item.tags),
            })
        return prompts

    def get_stats(self) -> Dict[str, Any]:
        """获取服务器统计信息"""
        return {
            "name": self.name,
            "version": self.version,
            "running": self._is_running,
            "tools": len(self.get_tools()),
            "resources": len(self.get_resources()),
            "prompts": len(self.get_prompts()),
            "middlewares": len(self.middleware_chain),
        }

    def __repr__(self) -> str:
        return f"MCPServer(name='{self.name}', version='{self.version}', running={self._is_running})"

    def _get_function_source_info(self, func: Callable) -> Optional[str]:
        """
        获取函数的源代码位置信息

        Args:
            func: 函数对象

        Returns:
            源代码位置字符串，格式为 "filename:lineno:column"，如果无法获取则返回 None
        """
        try:
            source_file = inspect.getsourcefile(func)
            if not source_file:
                return None

            try:
                import pathlib
                import os
                project_root = pathlib.Path(__file__).parent.parent.parent.parent.resolve()
                rel_path = os.path.relpath(source_file, str(project_root))
            except Exception:
                rel_path = source_file

            _, lineno = inspect.getsourcelines(func)

            column = None
            try:
                lines, start_lineno = inspect.findsource(func)
                if lines:
                    func_line = lines[start_lineno - 1]
                    def_pos = func_line.find("def ")
                    if def_pos != -1:
                        column = def_pos
            except Exception:
                pass

            if column is not None:
                return f"{rel_path}:{lineno}:{column}"
            else:
                return f"{rel_path}:{lineno}"

        except Exception:
            return None


def create_server(
    name: Optional[str] = None,
    version: Optional[str] = None,
    **kwargs,
) -> MCPServer:
    """
    创建 MCP 服务器的便捷函数

    Args:
        name: 服务器名称
        version: 服务器版本
        **kwargs: 传递给 MCPServer 的其他参数

    Returns:
        MCPServer 实例
    """
    return MCPServer(name, version, **kwargs)
