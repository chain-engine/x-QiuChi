"""
统一注册表（注册组件）

插件注册中心，负责工具 / 资源 / 提示词的统一注册、分类管理与元数据存储：
- 实例挂在 server.registry（PluginRegistry("ServerRegistry")），由 PluginManager 写入
- 进程级默认实例 global_registry 供无 server 场景直接使用
- RLock 保证线程安全
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from threading import RLock
from typing import Any

from src.constants import PluginType
from src.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PluginMetadata:
    """插件元数据（注册表条目元数据，PluginManager._register_item 构造）"""

    name: str
    description: str = ""
    category: str = "default"
    subcategory: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class RegistryItem:
    """注册表项"""

    name: str
    item: Any
    type: PluginType
    metadata: PluginMetadata
    category: str = "default"
    subcategory: str | None = None
    tags: set[str] = field(default_factory=set)
    is_enabled: bool = True


class PluginRegistry:
    """插件注册中心（注册组件）

    由 PluginManager._register_item 写入、MCP 调用方读取；
    不感知 Discovery / Collector，注册表只负责存储与查询。
    """

    def __init__(self, name: str = "PluginRegistry"):
        self.name = name
        self._items: dict[str, RegistryItem] = {}
        self._lock = RLock()
        logger.debug(f"Initialized registry: {name}")

    def register(
        self,
        name: str,
        item: Any,
        item_type: PluginType,
        metadata: PluginMetadata,
        *,
        category: str = "default",
        subcategory: str | None = None,
        tags: list[str] | None = None,
        enabled: bool = True,
        overwrite: bool = False,
    ) -> bool:
        """注册一个插件项（同名默认拒绝，overwrite=True 时覆盖）"""
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
                f"[{self.name}] Registered: {name} (type={item_type}, category={category})"
            )
            return True

    def register_tool(self, name: str, tool: Callable, metadata: PluginMetadata, **kwargs) -> bool:
        """注册工具"""
        return self.register(name, tool, PluginType.TOOL, metadata, **kwargs)

    def register_resource(
        self, name: str, resource: Callable, metadata: PluginMetadata, **kwargs
    ) -> bool:
        """注册资源"""
        return self.register(name, resource, PluginType.RESOURCE, metadata, **kwargs)

    def register_prompt(
        self, name: str, prompt: Callable, metadata: PluginMetadata, **kwargs
    ) -> bool:
        """注册提示词"""
        return self.register(name, prompt, PluginType.PROMPT, metadata, **kwargs)

    def unregister(self, name: str) -> bool:
        with self._lock:
            if name in self._items:
                del self._items[name]
                logger.debug(f"[{self.name}] Unregistered: {name}")
                return True
            return False

    def get(self, name: str) -> Any | None:
        with self._lock:
            item = self._items.get(name)
            return item.item if item and item.is_enabled else None

    def get_item(self, name: str, enabled_only: bool = True) -> RegistryItem | None:
        with self._lock:
            item = self._items.get(name)
            if enabled_only and item and not item.is_enabled:
                return None
            return item

    def get_all(
        self,
        item_type: PluginType | None = None,
        category: str | None = None,
        subcategory: str | None = None,
        tags: list[str] | None = None,
        enabled_only: bool = True,
    ) -> list[Any]:
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
        item_type: PluginType | None = None,
        category: str | None = None,
        subcategory: str | None = None,
        tags: list[str] | None = None,
        enabled_only: bool = True,
    ) -> list[RegistryItem]:
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

    def get_all_items_by_str_type(
        self,
        item_type_str: str,
        category: str | None = None,
        subcategory: str | None = None,
        tags: list[str] | None = None,
        enabled_only: bool = True,
    ) -> list[RegistryItem]:
        """通过字符串类型名查询（"tool" / "resource" / "prompt"）。"""
        with self._lock:
            items = []
            for item in self._items.values():
                if enabled_only and not item.is_enabled:
                    continue
                if item.type.value != item_type_str:
                    continue
                if category and item.category != category:
                    continue
                if subcategory and item.subcategory != subcategory:
                    continue
                if tags and not any(tag in item.tags for tag in tags):
                    continue
                items.append(item)
            return items

    def get_tools(
        self, category: str | None = None, subcategory: str | None = None, enabled_only: bool = True
    ) -> list[Callable]:
        """获取工具列表"""
        return self.get_all(PluginType.TOOL, category, subcategory, enabled_only=enabled_only)

    def get_resources(
        self, category: str | None = None, subcategory: str | None = None, enabled_only: bool = True
    ) -> list[Callable]:
        """获取资源列表"""
        return self.get_all(PluginType.RESOURCE, category, subcategory, enabled_only=enabled_only)

    def get_prompts(
        self, category: str | None = None, subcategory: str | None = None, enabled_only: bool = True
    ) -> list[Callable]:
        """获取提示词列表"""
        return self.get_all(PluginType.PROMPT, category, subcategory, enabled_only=enabled_only)

    def enable(self, name: str) -> bool:
        """启用指定注册项"""
        with self._lock:
            if name in self._items:
                self._items[name].is_enabled = True
                logger.debug(f"[{self.name}] Enabled: {name}")
                return True
            return False

    def disable(self, name: str) -> bool:
        """禁用指定注册项"""
        with self._lock:
            if name in self._items:
                self._items[name].is_enabled = False
                logger.debug(f"[{self.name}] Disabled: {name}")
                return True
            return False

    def contains(self, name: str) -> bool:
        """是否已注册该名称"""
        with self._lock:
            return name in self._items

    def list_names(
        self,
        item_type: PluginType | None = None,
        category: str | None = None,
        subcategory: str | None = None,
        enabled_only: bool = True,
    ) -> list[str]:
        """按类型 / 分类 / 子分类列出注册项名称"""
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

    def list_categories(self, item_type: PluginType | None = None) -> list[str]:
        """列出全部分类（可按类型过滤）"""
        with self._lock:
            categories = set()
            for item in self._items.values():
                if item_type and item.type != item_type:
                    continue
                categories.add(item.category)
            return sorted(categories)

    def count(
        self,
        item_type: PluginType | None = None,
        category: str | None = None,
        subcategory: str | None = None,
        enabled_only: bool = True,
    ) -> int:
        """统计注册项数量（可按类型 / 分类 / 子分类过滤）"""
        with self._lock:
            return len(
                self.get_all_items(item_type, category, subcategory, enabled_only=enabled_only)
            )

    def clear(self) -> None:
        """清空全部注册项"""
        with self._lock:
            self._items.clear()
            logger.debug(f"[{self.name}] Registry cleared")

    def print_info(self) -> None:
        """打印注册表统计信息（总量 / 启用数 / 按类型与分类分布）"""
        with self._lock:
            total = len(self._items)
            enabled = sum(1 for item in self._items.values() if item.is_enabled)
            logger.info(f"[{self.name}] Total items: {total} (enabled: {enabled})")

            type_stats: dict[PluginType, int] = {}
            for item in self._items.values():
                type_stats[item.type] = type_stats.get(item.type, 0) + 1

            for item_type, count in sorted(type_stats.items()):
                logger.info(f"  - {item_type.value}: {count}")

            category_stats: dict[str, int] = {}
            for item in self._items.values():
                category_stats[item.category] = category_stats.get(item.category, 0) + 1

            for category, count in sorted(category_stats.items()):
                logger.info(f"    * {category}: {count}")


global_registry = PluginRegistry("GlobalRegistry")
