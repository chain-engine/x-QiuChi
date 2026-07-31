"""
QiuChi 插件管理器

负责插件的：
- 自动发现（扫描 discovery_paths 中的模块）
- 依赖解析（按拓扑排序加载）
- 生命周期管理（load → enable → disable → unload）
- 启用/禁用配置（结合 settings.plugins.enabled_plugins / disabled_plugins）

注意：基于装饰器（@tool/@resource/@prompt）的轻量级插件由 plugins.collector 处理，
本管理器主要管理基于 Plugin 类的重型插件，同时也提供 disable/enable 列表的统一处理。
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from core.config.config import settings
from core.logging.logger import get_logger

from .base import PluginStatus, PluginType
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
        self._discovered: Set[str] = set()

    # ------------------------------------------------------------------
    # 基础查询
    # ------------------------------------------------------------------
    @property
    def plugins(self) -> List[Plugin]:
        return self.loader.get_all()

    def get_plugin(self, name: str) -> Optional[Plugin]:
        return self.loader.get(name)

    def get_by_type(self, plugin_type: PluginType) -> List[Plugin]:
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

    def discover(self, paths: Optional[List[str]] = None) -> List[str]:
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
    def _ordered_by_dependency(self) -> List[Plugin]:
        """拓扑排序：依赖在前，被依赖在后"""
        plugins = self.loader.get_all()
        name_to_plugin = {p.name: p for p in plugins}
        visited: Set[str] = set()
        ordered: List[Plugin] = []

        def visit(name: str, stack: Set[str]) -> None:
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

    # ------------------------------------------------------------------
    # 统计
    # ------------------------------------------------------------------
    def stats(self) -> Dict[str, Any]:
        type_counts: Dict[str, int] = {}
        status_counts: Dict[str, int] = {}
        for plugin in self.loader.get_all():
            type_counts[plugin.type.value] = type_counts.get(plugin.type.value, 0) + 1
            status_counts[plugin.status.value] = status_counts.get(plugin.status.value, 0) + 1
        return {
            "total": len(self.loader.get_all()),
            "by_type": type_counts,
            "by_status": status_counts,
        }


__all__ = ["PluginManager"]
