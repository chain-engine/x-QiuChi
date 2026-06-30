"""
QiuChi 统一注册表

提供统一的插件注册和发现机制，支持：
- 工具、资源、提示词统一注册
- 分类和子分类管理
- 元数据存储
- 线程安全
"""

from typing import Any, Dict, List, Optional, Set, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
from threading import RLock
import inspect

from .base import PluginType, PluginMetadata
from ..logging.logger import get_logger

logger = get_logger(__name__)


class RegistryItemType(str, Enum):
    """注册表项类型"""
    TOOL = "tool"
    RESOURCE = "resource"
    PROMPT = "prompt"


@dataclass
class RegistryItem:
    """注册表项"""
    name: str
    item: Any  # 可以是函数、类或任何可调用对象
    type: RegistryItemType
    metadata: PluginMetadata
    category: str = "default"
    subcategory: Optional[str] = None
    tags: Set[str] = field(default_factory=set)
    is_enabled: bool = True


class PluginRegistry:
    """
    插件注册中心

    管理所有已注册的插件项，支持分类、过滤和查询。
    """

    def __init__(self, name: str = "PluginRegistry"):
        """
        初始化注册表

        Args:
            name: 注册表名称，用于日志
        """
        self.name = name
        self._items: Dict[str, RegistryItem] = {}
        self._lock = RLock()
        logger.debug(f"Initialized registry: {name}")

    def register(
        self,
        name: str,
        item: Any,
        item_type: RegistryItemType,
        metadata: PluginMetadata,
        *,
        category: str = "default",
        subcategory: Optional[str] = None,
        tags: Optional[List[str]] = None,
        enabled: bool = True,
        overwrite: bool = False,
    ) -> bool:
        """
        注册一个项目

        Args:
            name: 项目名称
            item: 项目对象（函数、类等）
            item_type: 项目类型
            metadata: 插件元数据
            category: 分类
            subcategory: 子分类
            tags: 标签列表
            enabled: 是否启用
            overwrite: 是否覆盖已存在的项目

        Returns:
            是否注册成功
        """
        with self._lock:
            if name in self._items and not overwrite:
                logger.debug(f"[{self.name}] Item '{name}' already exists, skipping")
                return False

            self._items[name] = RegistryItem(
                name=name,
                item=item,
                type=item_type,
                metadata=metadata,
                category=category,
                subcategory=subcategory,
                tags=set(tags or []),
                is_enabled=enabled,
            )
            logger.debug(
                f"[{self.name}] Registered: {name} "
                f"(type={item_type}, category={category}, subcategory={subcategory})"
            )
            return True

    def unregister(self, name: str) -> bool:
        """
        注销一个项目

        Args:
            name: 项目名称

        Returns:
            是否注销成功
        """
        with self._lock:
            if name in self._items:
                del self._items[name]
                logger.debug(f"[{self.name}] Unregistered: {name}")
                return True
            return False

    def get(self, name: str) -> Optional[Any]:
        """
        获取项目

        Args:
            name: 项目名称

        Returns:
            项目对象，不存在返回 None
        """
        with self._lock:
            item = self._items.get(name)
            return item.item if item and item.is_enabled else None

    def get_item(self, name: str, enabled_only: bool = True) -> Optional[RegistryItem]:
        """
        获取注册表项（包含元数据）

        Args:
            name: 项目名称
            enabled_only: 是否只返回启用的项目（默认 True，与 get() 行为一致）

        Returns:
            注册表项，不存在或未启用（当 enabled_only=True 时）返回 None
        """
        with self._lock:
            item = self._items.get(name)
            if enabled_only and item and not item.is_enabled:
                return None
            return item

    def get_all(
        self,
        item_type: Optional[RegistryItemType] = None,
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
        tags: Optional[List[str]] = None,
        enabled_only: bool = True,
    ) -> List[Any]:
        """
        获取所有项目

        Args:
            item_type: 按类型过滤
            category: 按分类过滤
            subcategory: 按子分类过滤
            tags: 按标签过滤（包含任意一个标签即可）
            enabled_only: 是否只返回启用的项目

        Returns:
            项目列表
        """
        with self._lock:
            items = []
            for item in self._items.values():
                if enabled_only and not item.is_enabled:
                    continue
                if item_type and item.type != item_type:
                    continue
                if category and item.category != category:
                    continue
                if subcategory and item.subcategory != subcategory:
                    continue
                if tags and not any(tag in item.tags for tag in tags):
                    continue
                items.append(item.item)
            return items

    def get_all_items(
        self,
        item_type: Optional[RegistryItemType] = None,
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
        tags: Optional[List[str]] = None,
        enabled_only: bool = True,
    ) -> List[RegistryItem]:
        """
        获取所有注册表项（包含元数据）

        Args:
            item_type: 按类型过滤
            category: 按分类过滤
            subcategory: 按子分类过滤
            tags: 按标签过滤
            enabled_only: 是否只返回启用的项目

        Returns:
            注册表项列表
        """
        with self._lock:
            items = []
            for item in self._items.values():
                if enabled_only and not item.is_enabled:
                    continue
                if item_type and item.type != item_type:
                    continue
                if category and item.category != category:
                    continue
                if subcategory and item.subcategory != subcategory:
                    continue
                if tags and not any(tag in item.tags for tag in tags):
                    continue
                items.append(item)
            return items

    def enable(self, name: str) -> bool:
        """
        启用项目

        Args:
            name: 项目名称

        Returns:
            是否启用成功
        """
        with self._lock:
            if name in self._items:
                self._items[name].is_enabled = True
                logger.debug(f"[{self.name}] Enabled: {name}")
                return True
            return False

    def disable(self, name: str) -> bool:
        """
        禁用项目

        Args:
            name: 项目名称

        Returns:
            是否禁用成功
        """
        with self._lock:
            if name in self._items:
                self._items[name].is_enabled = False
                logger.debug(f"[{self.name}] Disabled: {name}")
                return True
            return False

    def contains(self, name: str) -> bool:
        """
        检查项目是否存在

        Args:
            name: 项目名称

        Returns:
            是否存在
        """
        with self._lock:
            return name in self._items

    def list_names(
        self,
        item_type: Optional[RegistryItemType] = None,
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
        enabled_only: bool = True,
    ) -> List[str]:
        """
        列出所有项目名称

        Args:
            item_type: 按类型过滤
            category: 按分类过滤
            subcategory: 按子分类过滤
            enabled_only: 是否只返回启用的项目

        Returns:
            名称列表
        """
        with self._lock:
            names = []
            for item in self._items.values():
                if enabled_only and not item.is_enabled:
                    continue
                if item_type and item.type != item_type:
                    continue
                if category and item.category != category:
                    continue
                if subcategory and item.subcategory != subcategory:
                    continue
                names.append(item.name)
            return names

    def list_categories(self, item_type: Optional[RegistryItemType] = None) -> List[str]:
        """
        列出所有分类

        Args:
            item_type: 按类型过滤

        Returns:
            分类列表
        """
        with self._lock:
            categories = set()
            for item in self._items.values():
                if item_type and item.type != item_type:
                    continue
                categories.add(item.category)
            return sorted(categories)

    def count(
        self,
        item_type: Optional[RegistryItemType] = None,
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
        enabled_only: bool = True,
    ) -> int:
        """
        统计项目数量

        Args:
            item_type: 按类型过滤
            category: 按分类过滤
            subcategory: 按子分类过滤
            enabled_only: 是否只统计启用的项目

        Returns:
            数量
        """
        with self._lock:
            return len(self.get_all_items(item_type, category, subcategory, enabled_only=enabled_only))

    def clear(self) -> None:
        """清空注册表"""
        with self._lock:
            self._items.clear()
            logger.debug(f"[{self.name}] Registry cleared")

    def print_info(self) -> None:
        """打印注册表信息"""
        with self._lock:
            total = len(self._items)
            enabled = sum(1 for item in self._items.values() if item.is_enabled)

            logger.info(f"[{self.name}] Total items: {total} (enabled: {enabled})")

            # 按类型统计
            type_stats: Dict[RegistryItemType, int] = {}
            for item in self._items.values():
                type_stats[item.type] = type_stats.get(item.type, 0) + 1

            for item_type, count in sorted(type_stats.items()):
                logger.info(f"  - {item_type.value}: {count}")

            # 按分类统计
            category_stats: Dict[str, int] = {}
            for item in self._items.values():
                category_stats[item.category] = category_stats.get(item.category, 0) + 1

            for category, count in sorted(category_stats.items()):
                logger.info(f"    * {category}: {count}")


class UnifiedRegistry:
    """
    统一注册表

    提供更高级的 API，统一管理工具、资源和提示词。
    """

    def __init__(self):
        self._registry = PluginRegistry("UnifiedRegistry")
        self._type_map = {
            PluginType.TOOL: RegistryItemType.TOOL,
            PluginType.RESOURCE: RegistryItemType.RESOURCE,
            PluginType.PROMPT: RegistryItemType.PROMPT,
        }

    def register_tool(
        self,
        name: str,
        tool: Callable,
        metadata: PluginMetadata,
        **kwargs,
    ) -> bool:
        """
        注册工具

        Args:
            name: 工具名称
            tool: 工具函数
            metadata: 插件元数据
            **kwargs: 传递给 register 的其他参数

        Returns:
            是否注册成功
        """
        return self._registry.register(
            name=name,
            item=tool,
            item_type=RegistryItemType.TOOL,
            metadata=metadata,
            **kwargs,
        )

    def register_resource(
        self,
        name: str,
        resource: Callable,
        metadata: PluginMetadata,
        **kwargs,
    ) -> bool:
        """
        注册资源

        Args:
            name: 资源名称（通常是 URI）
            resource: 资源函数
            metadata: 插件元数据
            **kwargs: 传递给 register 的其他参数

        Returns:
            是否注册成功
        """
        return self._registry.register(
            name=name,
            item=resource,
            item_type=RegistryItemType.RESOURCE,
            metadata=metadata,
            **kwargs,
        )

    def register_prompt(
        self,
        name: str,
        prompt: Callable,
        metadata: PluginMetadata,
        **kwargs,
    ) -> bool:
        """
        注册提示词

        Args:
            name: 提示词名称
            prompt: 提示词函数
            metadata: 插件元数据
            **kwargs: 传递给 register 的其他参数

        Returns:
            是否注册成功
        """
        return self._registry.register(
            name=name,
            item=prompt,
            item_type=RegistryItemType.PROMPT,
            metadata=metadata,
            **kwargs,
        )

    def get_tools(
        self,
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
        enabled_only: bool = True,
    ) -> List[Callable]:
        """
        获取工具列表

        Args:
            category: 按分类过滤
            subcategory: 按子分类过滤
            enabled_only: 是否只返回启用的工具

        Returns:
            工具列表
        """
        return self._registry.get_all(
            item_type=RegistryItemType.TOOL,
            category=category,
            subcategory=subcategory,
            enabled_only=enabled_only,
        )

    def get_resources(
        self,
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
        enabled_only: bool = True,
    ) -> List[Callable]:
        """
        获取资源列表

        Args:
            category: 按分类过滤
            subcategory: 按子分类过滤
            enabled_only: 是否只返回启用的资源

        Returns:
            资源列表
        """
        return self._registry.get_all(
            item_type=RegistryItemType.RESOURCE,
            category=category,
            subcategory=subcategory,
            enabled_only=enabled_only,
        )

    def get_prompts(
        self,
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
        enabled_only: bool = True,
    ) -> List[Callable]:
        """
        获取提示词列表

        Args:
            category: 按分类过滤
            subcategory: 按子分类过滤
            enabled_only: 是否只返回启用的提示词

        Returns:
            提示词列表
        """
        return self._registry.get_all(
            item_type=RegistryItemType.PROMPT,
            category=category,
            subcategory=subcategory,
            enabled_only=enabled_only,
        )

    # 代理方法到内部注册表
    def __getattr__(self, name: str) -> Any:
        """代理未定义的方法到内部注册表"""
        return getattr(self._registry, name)


# 全局统一注册表实例
global_registry = UnifiedRegistry()