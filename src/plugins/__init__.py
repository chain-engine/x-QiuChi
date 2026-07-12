"""
QiuChi 插件系统

提供统一的插件管理框架，支持：
- 装饰器注册（@tool, @resource, @prompt）
- 插件管理器（PluginManager）
- 统一注册表（UnifiedRegistry）

注册方式：
    @tool(category="math")
    def add(a, b): return a + b
"""

from .base import PluginType, PluginMetadata, PluginStatus
from .decorators import (
    tool, resource, prompt,
    get_tool_collector, get_resource_collector, get_prompt_collector,
    PluginCollector,
)
from .registry import PluginRegistry, UnifiedRegistry, RegistryItemType
from .manager import PluginManager

__all__ = [
    "PluginType",
    "PluginMetadata",
    "PluginStatus",
    "tool",
    "resource",
    "prompt",
    "get_tool_collector",
    "get_resource_collector",
    "get_prompt_collector",
    "PluginCollector",
    "PluginRegistry",
    "UnifiedRegistry",
    "RegistryItemType",
    "PluginManager",
]
