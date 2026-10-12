"""
插件收集器（收集组件）

负责装饰器函数插件（@tool/@resource/@prompt）的收集，进程级全局单例：
- PluginCollector：收集器核心（线程安全，按插件类型各持一份）
- @tool/@resource/@prompt 装饰器：标记函数并写入全局收集器

与 PluginManager 的关系：本模块是"被动写入、主动读取"的数据源。
写入发生在模块 import 时（装饰器副作用，无需显式调用）；
读取发生在 PluginManager.initialize() 注册阶段（get_*_collector().get_items()）。
收集器不感知 PluginDiscovery / PluginRegistry，三者由 PluginManager 串联。
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar, cast

from src.constants import PluginType

T = TypeVar("T")
FuncType = Callable[..., Any]


class PluginCollector:
    """插件项收集器（线程安全；单个收集器服务于一种插件类型）"""

    def __init__(self, plugin_type: PluginType):
        self.plugin_type = plugin_type
        self._items: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def collect(self, func: FuncType, name: str | None = None, **metadata):
        """收集一个插件函数：注入插件元数据并存入 _items。

        由装饰器在模块 import 时调用；返回带 _is_plugin_item 标记的
        wrapper（PluginDiscovery 据此识别装饰器函数插件）。
        """
        func_name = name or func.__name__
        func_doc = func.__doc__ or ""

        @wraps(func)
        def _inner(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        # 运行时动态注入插件元数据（mypy 无法感知，显式标注为 Any）
        wrapper: Any = _inner
        wrapper._is_plugin_item = True
        wrapper._plugin_type = self.plugin_type.value
        wrapper._plugin_name = func_name
        wrapper._plugin_category = metadata.get("category", "default")
        wrapper._plugin_subcategory = metadata.get("subcategory")
        wrapper._plugin_tags = metadata.get("tags", [])
        wrapper._plugin_metadata = metadata
        wrapper._plugin_func = func

        with self._lock:
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

    def get_items(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return self._items.copy()


# 全局收集器：进程内唯一，每插件类型一个实例（第一版不隔离多 server）
_collectors: dict[PluginType, PluginCollector] = {
    PluginType.TOOL: PluginCollector(PluginType.TOOL),
    PluginType.RESOURCE: PluginCollector(PluginType.RESOURCE),
    PluginType.PROMPT: PluginCollector(PluginType.PROMPT),
}


def get_tool_collector() -> PluginCollector:
    return _collectors[PluginType.TOOL]


def get_resource_collector() -> PluginCollector:
    return _collectors[PluginType.RESOURCE]


def get_prompt_collector() -> PluginCollector:
    return _collectors[PluginType.PROMPT]


def _make_decorator(plugin_type: PluginType):
    """构造指定插件类型的装饰器工厂（tool/resource/prompt 共用实现）"""

    def factory(
        name: str | None = None,
        category: str = "default",
        subcategory: str | None = None,
        tags: list | None = None,
        **metadata,
    ) -> Callable[[FuncType], FuncType]:
        def decorator(func: FuncType) -> FuncType:
            wrapper = _collectors[plugin_type].collect(
                func,
                name=name,
                category=category,
                subcategory=subcategory,
                tags=tags or [],
                **metadata,
            )
            return cast(Callable[..., Any], wrapper)

        return decorator

    return factory


# 公共装饰器
tool = _make_decorator(PluginType.TOOL)
resource = _make_decorator(PluginType.RESOURCE)
prompt = _make_decorator(PluginType.PROMPT)
