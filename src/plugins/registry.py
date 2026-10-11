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

    def get(self, name: str) -> Any | None:
        with self._lock:
            item = self._items.get(name)
            return item.item if item else None

    def get_item(self, name: str) -> RegistryItem | None:
        with self._lock:
            return self._items.get(name)

    def get_all(
        self,
        item_type: PluginType | None = None,
        category: str | None = None,
        subcategory: str | None = None,
        tags: list[str] | None = None,
    ) -> list[Any]:
        with self._lock:
            items = []
            for item in self._items.values():
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
    ) -> list[RegistryItem]:
        with self._lock:
            items = []
            for item in self._items.values():
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

    def get_tools(
        self, category: str | None = None, subcategory: str | None = None
    ) -> list[Callable]:
        """获取工具列表"""
        return self.get_all(PluginType.TOOL, category, subcategory)

    def get_resources(
        self, category: str | None = None, subcategory: str | None = None
    ) -> list[Callable]:
        """获取资源列表"""
        return self.get_all(PluginType.RESOURCE, category, subcategory)

    def get_prompts(
        self, category: str | None = None, subcategory: str | None = None
    ) -> list[Callable]:
        """获取提示词列表"""
        return self.get_all(PluginType.PROMPT, category, subcategory)

    def list_names(
        self,
        item_type: PluginType | None = None,
        category: str | None = None,
        subcategory: str | None = None,
    ) -> list[str]:
        """按类型 / 分类 / 子分类列出注册项名称"""
        with self._lock:
            names = []
            for item in self._items.values():
                if item_type and item.type != item_type:
                    continue
                if category and item.category != category:
                    continue
                if subcategory and item.subcategory != subcategory:
                    continue
                names.append(item.name)
            return names

    def count(
        self,
        item_type: PluginType | None = None,
        category: str | None = None,
        subcategory: str | None = None,
    ) -> int:
        """统计注册项数量（可按类型 / 分类 / 子分类过滤）"""
        with self._lock:
            return len(self.get_all_items(item_type, category, subcategory))

    def clear(self) -> None:
        """清空全部注册项"""
        with self._lock:
            self._items.clear()
            logger.debug(f"[{self.name}] Registry cleared")


global_registry = PluginRegistry("GlobalRegistry")
