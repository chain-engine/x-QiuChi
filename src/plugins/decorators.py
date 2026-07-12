"""
QiuChi 插件装饰器

提供 @tool、@resource、@prompt 装饰器，用于快速注册插件项。

使用方式：
    @tool(category="math")
    def add(a: float, b: float) -> float:
        return a + b

注册机制：
    1. 装饰器执行时，将函数信息暂存到全局收集器
    2. 服务器启动时，从收集器读取并注册到注册表
"""

from typing import Any, Callable, Dict, Optional, TypeVar
from functools import wraps

from .base import PluginType

T = TypeVar("T")
FuncType = Callable[..., Any]


class PluginCollector:
    """
    插件项收集器

    装饰器使用的全局收集器，负责暂存被装饰的函数信息。
    服务器启动时从这里读取所有已收集的项并注册到系统。
    """

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


_tool_collector: Optional[PluginCollector] = None
_resource_collector: Optional[PluginCollector] = None
_prompt_collector: Optional[PluginCollector] = None


def _get_collector(plugin_type: str) -> PluginCollector:
    """获取指定类型的收集器（单例模式）"""
    global _tool_collector, _resource_collector, _prompt_collector

    type_map = {
        "tool": (_tool_collector, PluginType.TOOL, lambda: _tool_collector.__set__(None, PluginCollector(PluginType.TOOL))),
        "resource": (_resource_collector, PluginType.RESOURCE, lambda: _resource_collector.__set__(None, PluginCollector(PluginType.RESOURCE))),
        "prompt": (_prompt_collector, PluginType.PROMPT, lambda: _prompt_collector.__set__(None, PluginCollector(PluginType.PROMPT))),
    }

    instance, enum_type, create_func = type_map[plugin_type]
    if instance is None:
        instance = PluginCollector(enum_type)
        if plugin_type == "tool":
            _tool_collector = instance
        elif plugin_type == "resource":
            _resource_collector = instance
        elif plugin_type == "prompt":
            _prompt_collector = instance
    return instance


def get_tool_collector() -> PluginCollector:
    """获取工具收集器"""
    return _get_collector("tool")


def get_resource_collector() -> PluginCollector:
    """获取资源收集器"""
    return _get_collector("resource")


def get_prompt_collector() -> PluginCollector:
    """获取提示词收集器"""
    return _get_collector("prompt")


def tool(
    name: Optional[str] = None,
    category: str = "default",
    subcategory: Optional[str] = None,
    tags: Optional[list[str]] = None,
    **metadata,
) -> Callable[[FuncType], FuncType]:
    """
    工具装饰器

    将函数标记为工具，自动收集到工具收集器中。

    Args:
        name: 工具名称（默认使用函数名）
        category: 分类
        subcategory: 子分类
        tags: 标签列表
        **metadata: 额外元数据

    Example:
        @tool(category="math", tags=["arithmetic"])
        def add(a: float, b: float) -> float:
            return a + b
    """
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
    """
    资源装饰器

    将函数标记为资源，自动收集到资源收集器中。

    Args:
        name: 资源名称（通常是 URI，默认使用函数名）
        category: 分类
        subcategory: 子分类
        tags: 标签列表
        **metadata: 额外元数据

    Example:
        @resource(name="config://server", category="system")
        def get_server_config() -> str:
            return "{}"
    """
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
    """
    提示词装饰器

    将函数标记为提示词，自动收集到提示词收集器中。

    Args:
        name: 提示词名称（默认使用函数名）
        category: 分类
        subcategory: 子分类
        tags: 标签列表
        **metadata: 额外元数据

    Example:
        @prompt(category="greeting", tags=["welcome"])
        def greeting(name: str) -> str:
            return f"Hello, {name}!"
    """
    def decorator(func: FuncType) -> FuncType:
        return get_prompt_collector().collect(
            func, name=name, category=category, subcategory=subcategory, tags=tags or [], **metadata
        )
    return decorator
