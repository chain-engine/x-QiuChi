"""
插件管理器

负责插件的：
- 自动发现（扫描 discovery_paths 中的模块）
- 依赖解析（按拓扑排序加载）
- 生命周期管理（load → enable → disable → unload）
- 启用/禁用配置（结合 settings.plugins.enabled_plugins / disabled_plugins）
- 装饰器函数注册（@tool/@resource/@prompt 收集结果统一注册到 registry + FastMCP）

插件形态分两类：基于 Plugin 类的重型插件走 loader 全生命周期管理；
基于装饰器的轻量级函数由 collector 收集，本管理器在 initialize 时统一注册。
"""

from __future__ import annotations

import asyncio
import importlib
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Any

from src.constants import PluginType
from src.core.config import settings
from src.core.logger import get_logger
from src.core.middleware import RequestContext, ResponseContext

from .base import PluginMetadata, PluginStatus
from .loader import Plugin, PluginLoader

logger = get_logger(__name__)


class PluginManager:
    """
    插件管理器

    Args:
        server: MCPServer 实例，用于 attach 到插件
    """

    def __init__(self, server: Any):
        self.server = server
        self.loader = PluginLoader()
        self._discovered: set[str] = set()

    # ------------------------------------------------------------------
    # 基础查询
    # ------------------------------------------------------------------
    @property
    def plugins(self) -> list[Plugin]:
        return self.loader.get_all()

    def get_plugin(self, name: str) -> Plugin | None:
        return self.loader.get(name)

    def get_by_type(self, plugin_type: PluginType) -> list[Plugin]:
        return self.loader.get_by_type(plugin_type)

    # ------------------------------------------------------------------
    # 注册 / 发现
    # ------------------------------------------------------------------
    def register(self, plugin: Plugin) -> bool:
        """注册一个插件实例"""
        if self._is_disabled(plugin.name):
            logger.debug(f"Plugin '{plugin.name}' is in disabled_plugins, skipping")
            return False
        return self.loader.register(plugin)

    def discover(self, paths: list[str] | None = None) -> list[str]:
        """
        自动发现插件

        扫描配置的 discovery_paths，导入模块触发装饰器收集。

        Returns:
            发现的插件名称列表
        """
        discovery_paths = paths or settings.plugins.discovery_paths
        self._discovered.clear()

        for path in discovery_paths:
            try:
                module = importlib.import_module(path)
                module_path = Path(module.__file__).parent if module.__file__ else None
                if module_path:
                    self._scan_module(module, module_path)
            except ImportError as e:
                logger.warning(f"无法导入发现路径 {path}: {e}")

        logger.info(f"Auto-discovered {len(self._discovered)} plugin entries")
        return sorted(self._discovered)

    def _scan_module(self, module: Any, module_path: Path) -> None:
        for py_file in module_path.rglob("*.py"):
            if py_file.name.startswith("_"):
                continue
            relative = py_file.relative_to(module_path)
            parts = list(relative.parts[:-1])
            module_name = (
                f"{module.__name__}.{'.'.join(parts)}.{py_file.stem}"
                if parts
                else f"{module.__name__}.{py_file.stem}"
            )
            try:
                submodule = importlib.import_module(module_name)
                for attr_name in dir(submodule):
                    attr = getattr(submodule, attr_name)
                    if isinstance(attr, Plugin):
                        self._discovered.add(attr.name)
            except ImportError as e:
                logger.debug(f"无法导入子模块 {module_name}: {e}")

    # ------------------------------------------------------------------
    # 初始化与装饰器函数注册（轻量级插件）
    # ------------------------------------------------------------------
    async def initialize(self) -> None:
        """初始化插件系统：发现 → 加载 → 启用 → 注册装饰器函数到 registry + FastMCP。"""
        logger.info("Initializing plugin system...")

        if settings.plugins.auto_discovery:
            # Plugin 类发现（import 模块时装饰器函数一并收集进全局收集器）
            self.discover()
            self._discover_decorator_modules()

        await self.load_all()
        await self.enable_all()
        self._register_decorator_functions()

    def _discover_decorator_modules(self) -> None:
        """扫描发现路径 import 模块，触发 @tool/@resource/@prompt 收集。"""
        from .discovery import discover_plugins

        discover_plugins()

    def _should_register_func(self, name: str) -> bool:
        """装饰器函数注册过滤：未被禁用，且（白名单为空或已命中）。"""
        return not self._is_disabled(name) and self._is_enabled(name)

    def _register_decorator_functions(self) -> None:
        """将全局收集器中的装饰器函数统一注册到 registry + FastMCP。"""
        from .collector import get_prompt_collector, get_resource_collector, get_tool_collector

        for tool_name, info in get_tool_collector().get_items().items():
            if not self._should_register_func(tool_name):
                continue
            self._register_tool(tool_name, info)

        for resource_name, info in get_resource_collector().get_items().items():
            if not self._should_register_func(resource_name):
                continue
            self._register_resource(resource_name, info)

        for prompt_name, info in get_prompt_collector().get_items().items():
            if not self._should_register_func(prompt_name):
                continue
            self._register_prompt(prompt_name, info)

    def _build_middleware_wrapper(
        self,
        func: Callable,
        func_kind: str,
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
            from src.core.opentelemetry import get_request_id

            req = RequestContext(
                request={
                    "method": f"{func_kind}:{func_id}",
                    "id": get_request_id(),  # 传输层注入的真实 request_id
                    "params": kwargs,
                    "_args": args,
                    "_kwargs": kwargs,
                },
                server=self.server,
            )
            try:
                from src.runtime.context import get_current_context

                current = get_current_context()
                if current is not None:
                    req.metadata = dict(current.metadata)
            except Exception:
                pass

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

    def _register_tool(self, name: str, info: dict[str, Any]) -> None:
        wrapper = self._build_middleware_wrapper(info["func"], "tool", name)
        metadata = PluginMetadata(
            name=name,
            description=info["doc"],
            category=info["category"],
            subcategory=info["subcategory"],
            tags=info["tags"],
        )
        self.server.registry.register_tool(
            name=name,
            tool=wrapper,
            metadata=metadata,
            category=info["category"],
            subcategory=info["subcategory"],
            tags=info["tags"],
        )
        # 注册到 FastMCP：由 wrapper 承载中间件管道，schema 由 FastMCP 分析
        self.server.mcp.tool(name=name, description=info["doc"])(wrapper)
        logger.debug(f"Registered tool: {name}")

    def _register_resource(self, uri: str, info: dict[str, Any]) -> None:
        wrapper = self._build_middleware_wrapper(info["func"], "resource", uri)
        metadata = PluginMetadata(
            name=uri,
            description=info["doc"],
            category=info["category"],
            subcategory=info["subcategory"],
            tags=info["tags"],
        )
        self.server.registry.register_resource(
            name=uri,
            resource=wrapper,
            metadata=metadata,
            category=info["category"],
            subcategory=info["subcategory"],
            tags=info["tags"],
        )
        self.server.mcp.resource(uri, name=uri, description=info["doc"])(wrapper)
        logger.debug(f"Registered resource: {uri}")

    def _register_prompt(self, name: str, info: dict[str, Any]) -> None:
        wrapper = self._build_middleware_wrapper(info["func"], "prompt", name)
        metadata = PluginMetadata(
            name=name,
            description=info["doc"],
            category=info["category"],
            subcategory=info["subcategory"],
            tags=info["tags"],
        )
        self.server.registry.register_prompt(
            name=name,
            prompt=wrapper,
            metadata=metadata,
            category=info["category"],
            subcategory=info["subcategory"],
            tags=info["tags"],
        )
        self.server.mcp.prompt(name=name, description=info["doc"])(wrapper)
        logger.debug(f"Registered prompt: {name}")

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    async def load_all(self) -> int:
        """加载所有已注册插件"""
        loaded = 0
        for plugin in self._ordered_by_dependency():
            if self._is_disabled(plugin.name):
                continue
            if not self._is_enabled(plugin.name):
                continue
            try:
                plugin.attach(self.server)
                await plugin.load()
                loaded += 1
            except Exception as e:
                plugin.status = PluginStatus.ERROR
                logger.error(f"Plugin '{plugin.name}' load failed: {e}")
        return loaded

    async def enable_all(self) -> int:
        """启用所有已加载插件"""
        enabled = 0
        for plugin in self._ordered_by_dependency():
            if plugin.status != PluginStatus.LOADED:
                continue
            if self._is_disabled(plugin.name) or not self._is_enabled(plugin.name):
                continue
            try:
                await plugin.enable()
                enabled += 1
            except Exception as e:
                plugin.status = PluginStatus.ERROR
                logger.error(f"Plugin '{plugin.name}' enable failed: {e}")
        return enabled

    async def disable_plugin(self, name: str) -> bool:
        plugin = self.loader.get(name)
        if not plugin:
            return False
        try:
            await plugin.disable()
            return True
        except Exception as e:
            logger.error(f"Plugin '{name}' disable failed: {e}")
            return False

    async def unload_plugin(self, name: str) -> bool:
        plugin = self.loader.get(name)
        if not plugin:
            return False
        try:
            await plugin.unload()
            return True
        except Exception as e:
            logger.error(f"Plugin '{name}' unload failed: {e}")
            return False

    async def shutdown(self) -> None:
        """优雅关闭所有插件"""
        for plugin in self.loader.get_all():
            try:
                if plugin.status in (PluginStatus.ENABLED,):
                    await plugin.disable()
                await plugin.unload()
            except Exception as e:
                logger.error(f"Plugin '{plugin.name}' shutdown error: {e}")

    # ------------------------------------------------------------------
    # 依赖解析
    # ------------------------------------------------------------------
    def _ordered_by_dependency(self) -> list[Plugin]:
        """拓扑排序：依赖在前，被依赖在后"""
        plugins = self.loader.get_all()
        name_to_plugin = {p.name: p for p in plugins}
        visited: set[str] = set()
        ordered: list[Plugin] = []

        def visit(name: str, stack: set[str]) -> None:
            if name in visited or name not in name_to_plugin:
                return
            if name in stack:
                logger.warning(f"Plugin dependency cycle detected at '{name}', skipping")
                return
            stack.add(name)
            plugin = name_to_plugin[name]
            for dep in plugin.metadata.dependencies:
                # dep 形式: "plugin_name" 或 "plugin_name@>=1.0.0"
                dep_name = dep.split("@", 1)[0]
                visit(dep_name, stack)
            stack.discard(name)
            visited.add(name)
            ordered.append(plugin)

        for plugin in plugins:
            visit(plugin.name, set())

        return ordered

    def _is_enabled(self, name: str) -> bool:
        """enabled_plugins 为空表示全部启用；否则仅启用列表中的"""
        enabled = settings.plugins.enabled_plugins
        return not enabled or name in enabled

    def _is_disabled(self, name: str) -> bool:
        return name in settings.plugins.disabled_plugins


__all__ = ["PluginManager"]
