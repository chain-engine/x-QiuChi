"""
QiuChi 插件装饰器

提供 @tool、@resource、@prompt 装饰器。

使用方式：
    @tool(category="math")
    def add(a: float, b: float) -> float:
        return a + b

注册流程：
    1. 装饰器执行时，将函数暂存到全局 Collector
    2. 服务器启动时，discover_plugins() 导入模块触发装饰器收集
    3. register_from_collectors() 从 Collector 读取并注册到注册表
"""

from typing import Any, Callable, Dict, Optional, TypeVar
from functools import wraps

from .base import PluginType

T = TypeVar("T")
FuncType = Callable[..., Any]


class PluginCollector:
    """插件项收集器"""

    def __init__(self, plugin_type: PluginType):
        self.plugin_type = plugin_type
        self._items: Dict[str, Dict[str, Any]] = {}

    def collect(self, func: FuncType, name: Optional[str] = None, **metadata):
        """收集一个插件项"""
        func_name = name or func.__name__
        func_doc = func.__doc__ or ""

        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        wrapper._is_plugin_item = True
        wrapper._plugin_type = self.plugin_type.value
        wrapper._plugin_name = func_name
        wrapper._plugin_category = metadata.get("category", "default")
        wrapper._plugin_subcategory = metadata.get("subcategory")
        wrapper._plugin_tags = metadata.get("tags", [])
        wrapper._plugin_metadata = metadata
        wrapper._plugin_func = func

        self._items[func_name] = {
            "name": func_name,
            "func": wrapper,
            "type": self.plugin_type,
            "category": metadata.get("category", "default"),
            "subcategory": metadata.get("subcategory"),
            "tags": metadata.get("tags", []),
            "metadata": metadata,
            "doc": func_doc,
        }

        return wrapper

    def get_items(self) -> Dict[str, Dict[str, Any]]:
        """获取所有已收集的项"""
        return self._items.copy()

    def clear(self) -> None:
        """清空收集器"""
        self._items.clear()


_tool_collector = PluginCollector(PluginType.TOOL)
_resource_collector = PluginCollector(PluginType.RESOURCE)
_prompt_collector = PluginCollector(PluginType.PROMPT)


def get_tool_collector() -> PluginCollector:
    """获取工具收集器"""
    return _tool_collector


def get_resource_collector() -> PluginCollector:
    """获取资源收集器"""
    return _resource_collector


def get_prompt_collector() -> PluginCollector:
    """获取提示词收集器"""
    return _prompt_collector


def tool(
    name: Optional[str] = None,
    category: str = "default",
    subcategory: Optional[str] = None,
    tags: Optional[list[str]] = None,
    **metadata,
) -> Callable[[FuncType], FuncType]:
    """工具装饰器"""
    def decorator(func: FuncType) -> FuncType:
        return get_tool_collector().collect(
            func, name=name, category=category, subcategory=subcategory, tags=tags or [], **metadata
        )
    return decorator


def resource(
    name: Optional[str] = None,
    category: str = "default",
    subcategory: Optional[str] = None,
    tags: Optional[list[str]] = None,
    **metadata,
) -> Callable[[FuncType], FuncType]:
    """资源装饰器"""
    def decorator(func: FuncType) -> FuncType:
        return get_resource_collector().collect(
            func, name=name, category=category, subcategory=subcategory, tags=tags or [], **metadata
        )
    return decorator


def prompt(
    name: Optional[str] = None,
    category: str = "default",
    subcategory: Optional[str] = None,
    tags: Optional[list[str]] = None,
    **metadata,
) -> Callable[[FuncType], FuncType]:
    """提示词装饰器"""
    def decorator(func: FuncType) -> FuncType:
        return get_prompt_collector().collect(
            func, name=name, category=category, subcategory=subcategory, tags=tags or [], **metadata
        )
    return decorator
