"""
QiuChi 插件收集器

提供插件项收集功能，包括：
- PluginCollector 类：收集器核心
- @tool, @resource, @prompt 装饰器：触发收集

注册流程：
    1. 使用 @tool/@resource/@prompt 装饰器标记函数
    2. 装饰器将函数收集到当前激活的收集器（按 server 隔离）
    3. 服务器启动时，从 Collector 读取并注册到注册表

注意：为了支持多服务器实例隔离，收集器按 server 实例进行分桶。
默认情况下使用全局收集器（向后兼容）。
"""

from __future__ import annotations

import threading
from typing import Any, Callable, Dict, Optional, TypeVar
from functools import wraps

from .base import PluginType

T = TypeVar("T")
FuncType = Callable[..., Any]


class PluginCollector:
    """插件项收集器（单 server 实例）"""

    def __init__(self, plugin_type: PluginType):
        self.plugin_type = plugin_type
        self._items: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def collect(self, func: FuncType, name: Optional[str] = None, **metadata):
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

    def get_items(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return self._items.copy()

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


# 全局（兜底）收集器，向后兼容
_tool_collector = PluginCollector(PluginType.TOOL)
_resource_collector = PluginCollector(PluginType.RESOURCE)
_prompt_collector = PluginCollector(PluginType.PROMPT)


# 多服务器隔离：按 server id 维护独立收集器
_collectors_by_server: Dict[int, Dict[PluginType, PluginCollector]] = {}
_active_server_id: Optional[int] = None
_global_lock = threading.Lock()


def register_server_collectors(server: Any) -> None:
    """为指定服务器注册独立的收集器组"""
    sid = id(server)
    with _global_lock:
        if sid not in _collectors_by_server:
            _collectors_by_server[sid] = {
                PluginType.TOOL: PluginCollector(PluginType.TOOL),
                PluginType.RESOURCE: PluginCollector(PluginType.RESOURCE),
                PluginType.PROMPT: PluginCollector(PluginType.PROMPT),
            }


def unregister_server_collectors(server: Any) -> None:
    """移除指定服务器的收集器"""
    sid = id(server)
    with _global_lock:
        _collectors_by_server.pop(sid, None)
        for tool_name, collector in _tool_collector._items.items() if False else []:
            pass
    # 同时清理全局收集器中该 server 装饰的项（通过 _source_server 标记）
    _prune_global(_tool_collector, sid)
    _prune_global(_resource_collector, sid)
    _prune_global(_prompt_collector, sid)


def _prune_global(collector: PluginCollector, server_id: int) -> None:
    """从全局收集器中移除指定 server 标记的项"""
    with collector._lock:
        items = collector._items
        to_remove = [k for k, v in items.items() if v.get("__source_server__") == server_id]
        for k in to_remove:
            items.pop(k, None)


def set_active_server(server: Optional[Any]) -> None:
    """设置当前激活的服务器（装饰器调用时使用）"""
    global _active_server_id
    _active_server_id = id(server) if server is not None else None


def _get_collector(plugin_type: PluginType) -> PluginCollector:
    """根据激活的 server 选择收集器"""
    if _active_server_id is not None:
        bucket = _collectors_by_server.get(_active_server_id)
        if bucket is not None:
            return bucket[plugin_type]
    # 兜底：全局收集器
    if plugin_type == PluginType.TOOL:
        return _tool_collector
    if plugin_type == PluginType.RESOURCE:
        return _resource_collector
    return _prompt_collector


def get_tool_collector() -> PluginCollector:
    return _get_collector(PluginType.TOOL)


def get_resource_collector() -> PluginCollector:
    return _get_collector(PluginType.RESOURCE)


def get_prompt_collector() -> PluginCollector:
    return _get_collector(PluginType.PROMPT)


def _make_decorator(plugin_type: PluginType):
    def factory(
        name: Optional[str] = None,
        category: str = "default",
        subcategory: Optional[str] = None,
        tags: Optional[list] = None,
        **metadata,
    ) -> Callable[[FuncType], FuncType]:
        def decorator(func: FuncType) -> FuncType:
            collector = _get_collector(plugin_type)
            wrapper = collector.collect(
                func, name=name, category=category, subcategory=subcategory, tags=tags or [], **metadata
            )
            # 标记来源 server，便于 unregister 时清理
            if _active_server_id is not None:
                items = collector._items
                if wrapper.__name__ in items:
                    items[wrapper.__name__]["__source_server__"] = _active_server_id
            return wrapper
        return decorator
    return factory


# 公共装饰器
tool = _make_decorator(PluginType.TOOL)
resource = _make_decorator(PluginType.RESOURCE)
prompt = _make_decorator(PluginType.PROMPT)


def get_all_tool_collectors() -> Dict[Optional[int], PluginCollector]:
    """获取所有工具收集器（按 server 隔离）"""
    result: Dict[Optional[int], PluginCollector] = {None: _tool_collector}
    for sid, bucket in _collectors_by_server.items():
        result[sid] = bucket[PluginType.TOOL]
    return result


def get_all_resource_collectors() -> Dict[Optional[int], PluginCollector]:
    result: Dict[Optional[int], PluginCollector] = {None: _resource_collector}
    for sid, bucket in _collectors_by_server.items():
        result[sid] = bucket[PluginType.RESOURCE]
    return result


def get_all_prompt_collectors() -> Dict[Optional[int], PluginCollector]:
    result: Dict[Optional[int], PluginCollector] = {None: _prompt_collector}
    for sid, bucket in _collectors_by_server.items():
        result[sid] = bucket[PluginType.PROMPT]
    return result
