"""
QiuChi 插件加载器

为基于类（而非装饰器）的插件提供统一加载接口。
"""

from __future__ import annotations

import abc
from typing import Any, Dict, List, Optional

from core.logging.logger import get_logger

from .base import PluginMetadata, PluginStatus, PluginType

logger = get_logger(__name__)


class Plugin(abc.ABC):
    """
    插件抽象基类

    用于需要拥有完整生命周期（load → enable → disable → unload）的插件。
    只需使用装饰器注册的工具/资源/提示词不强制继承该类。
    """

    def __init__(self, metadata: PluginMetadata):
        self.metadata = metadata
        self.status: PluginStatus = PluginStatus.UNLOADED
        self._server: Any = None

    @property
    def name(self) -> str:
        return self.metadata.name

    @property
    def type(self) -> PluginType:
        return self.metadata.type

    def attach(self, server: Any) -> None:
        """挂载服务器实例（load 之前调用）"""
        self._server = server

    async def load(self) -> None:
        """加载插件（可重写）"""
        self.status = PluginStatus.LOADED
        logger.debug(f"Plugin '{self.name}' loaded")

    async def enable(self) -> None:
        """启用插件"""
        self.status = PluginStatus.ENABLED
        logger.info(f"Plugin '{self.name}' enabled")

    async def disable(self) -> None:
        """禁用插件"""
        self.status = PluginStatus.DISABLED
        logger.info(f"Plugin '{self.name}' disabled")

    async def unload(self) -> None:
        """卸载插件"""
        self.status = PluginStatus.UNLOADED
        self._server = None
        logger.info(f"Plugin '{self.name}' unloaded")


class PluginLoader:
    """
    插件加载器

    负责对 `Plugin` 子类进行注册、查询和卸载（区别于通过装饰器收集的轻量级插件）。
    """

    def __init__(self) -> None:
        self._plugins: Dict[str, Plugin] = {}

    def register(self, plugin: Plugin) -> bool:
        if plugin.name in self._plugins:
            logger.warning(f"Plugin '{plugin.name}' already registered")
            return False
        self._plugins[plugin.name] = plugin
        logger.debug(f"Plugin '{plugin.name}' registered")
        return True

    def get(self, name: str) -> Optional[Plugin]:
        return self._plugins.get(name)

    def get_all(self) -> List[Plugin]:
        return list(self._plugins.values())

    def get_by_type(self, plugin_type: PluginType) -> List[Plugin]:
        return [p for p in self._plugins.values() if p.type == plugin_type]

    def remove(self, name: str) -> bool:
        return self._plugins.pop(name, None) is not None

    def clear(self) -> None:
        self._plugins.clear()


__all__ = ["Plugin", "PluginLoader"]
