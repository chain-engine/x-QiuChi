"""
QiuChi 插件装饰器基类

提供统一的插件装饰器实现，支持自动发现和注册。
"""

from typing import Any, Callable, Optional, Dict, TypeVar, Generic
from functools import wraps
from enum import Enum
import inspect

from ..core.plugins.base import PluginType, PluginMetadata

T = TypeVar("T")
FuncType = Callable[..., Any]


class PluginDecorator:
    """
    插件装饰器基类

    用于创建统一风格的插件装饰器。
    """

    def __init__(self, plugin_type: PluginType):
        self.plugin_type = plugin_type
        self._registered_items: Dict[str, Dict[str, Any]] = {}

    def __call__(
        self,
        name: Optional[str] = None,
        category: str = "default",
        subcategory: Optional[str] = None,
        tags: Optional[list[str]] = None,
        **metadata,
    ) -> Callable[[FuncType], FuncType]:
        """
        创建装饰器

        Args:
            name: 插件项名称
            category: 分类
            subcategory: 子分类
            tags: 标签列表
            **metadata: 额外元数据

        Returns:
            装饰器函数
        """
        def decorator(func: FuncType) -> FuncType:
            # 获取函数信息
            func_name = name or func.__name__
            func_doc = func.__doc__ or ""

            # 创建包装器
            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)

            # 标记为插件项
            wrapper._is_plugin_item = True
            wrapper._plugin_type = self.plugin_type.value
            wrapper._plugin_name = func_name
            wrapper._plugin_category = category
            wrapper._plugin_subcategory = subcategory
            wrapper._plugin_tags = tags or []
            wrapper._plugin_metadata = metadata
            wrapper._plugin_func = func

            # 存储注册信息
            self._registered_items[func_name] = {
                "name": func_name,
                "func": wrapper,
                "type": self.plugin_type,
                "category": category,
                "subcategory": subcategory,
                "tags": tags or [],
                "metadata": metadata,
                "doc": func_doc,
            }

            return wrapper

        return decorator

    def get_registered_items(self) -> Dict[str, Dict[str, Any]]:
        """获取所有已注册的项"""
        return self._registered_items.copy()

    def clear_registered_items(self) -> None:
        """清空已注册的项"""
        self._registered_items.clear()


# 创建特定类型的装饰器工厂
def create_plugin_decorator(plugin_type: str) -> PluginDecorator:
    """
    创建插件装饰器

    Args:
        plugin_type: 插件类型 ("tool", "resource", "prompt")

    Returns:
        PluginDecorator 实例
    """
    type_map = {
        "tool": PluginType.TOOL,
        "resource": PluginType.RESOURCE,
        "prompt": PluginType.PROMPT,
    }

    if plugin_type not in type_map:
        raise ValueError(f"Invalid plugin type: {plugin_type}. Valid options: {list(type_map.keys())}")

    return PluginDecorator(type_map[plugin_type])


# 全局装饰器实例（延迟创建）
_tool_decorator: Optional[PluginDecorator] = None
_resource_decorator: Optional[PluginDecorator] = None
_prompt_decorator: Optional[PluginDecorator] = None


def get_tool_decorator() -> PluginDecorator:
    """获取工具装饰器实例"""
    global _tool_decorator
    if _tool_decorator is None:
        _tool_decorator = create_plugin_decorator("tool")
    return _tool_decorator


def get_resource_decorator() -> PluginDecorator:
    """获取资源装饰器实例"""
    global _resource_decorator
    if _resource_decorator is None:
        _resource_decorator = create_plugin_decorator("resource")
    return _resource_decorator


def get_prompt_decorator() -> PluginDecorator:
    """获取提示词装饰器实例"""
    global _prompt_decorator
    if _prompt_decorator is None:
        _prompt_decorator = create_plugin_decorator("prompt")
    return _prompt_decorator


# 便捷函数
def tool(
    name: Optional[str] = None,
    category: str = "default",
    subcategory: Optional[str] = None,
    tags: Optional[list[str]] = None,
    **metadata,
) -> Callable[[FuncType], FuncType]:
    """
    工具装饰器

    Args:
        name: 工具名称
        category: 分类
        subcategory: 子分类
        tags: 标签列表
        **metadata: 额外元数据

    Returns:
        装饰器函数

    Example:
        >>> @tool(category="math")
        ... def add(a: float, b: float) -> float:
        ...     return a + b
    """
    return get_tool_decorator()(name, category, subcategory, tags, **metadata)


def resource(
    name: Optional[str] = None,
    category: str = "default",
    subcategory: Optional[str] = None,
    tags: Optional[list[str]] = None,
    **metadata,
) -> Callable[[FuncType], FuncType]:
    """
    资源装饰器

    Args:
        name: 资源名称（通常是 URI）
        category: 分类
        subcategory: 子分类
        tags: 标签列表
        **metadata: 额外元数据

    Returns:
        装饰器函数

    Example:
        >>> @resource(name="config://app", category="system")
        ... def get_config() -> str:
        ...     return "{}"
    """
    return get_resource_decorator()(name, category, subcategory, tags, **metadata)


def prompt(
    name: Optional[str] = None,
    category: str = "default",
    subcategory: Optional[str] = None,
    tags: Optional[list[str]] = None,
    **metadata,
) -> Callable[[FuncType], FuncType]:
    """
    提示词装饰器

    Args:
        name: 提示词名称
        category: 分类
        subcategory: 子分类
        tags: 标签列表
        **metadata: 额外元数据

    Returns:
        装饰器函数

    Example:
        >>> @prompt(category="general")
        ... def greeting(name: str) -> str:
        ...     return f"Hello, {name}!"
    """
    return get_prompt_decorator()(name, category, subcategory, tags, **metadata)