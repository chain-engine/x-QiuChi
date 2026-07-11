"""
QiuChi 插件系统

提供统一的插件管理框架，支持：
- 插件发现和加载
- 生命周期管理
- 依赖解析
- 统一注册表
"""

from .base import (
    Plugin, PluginType, PluginMetadata,
    tool, resource, prompt,
    PluginDecorator, create_plugin_decorator,
    get_tool_decorator, get_resource_decorator, get_prompt_decorator,
)
from .registry import PluginRegistry, UnifiedRegistry
from .manager import PluginManager
from .discovery import PluginDiscovery

__all__ = [
    "Plugin",
    "PluginType",
    "PluginMetadata",
    "PluginRegistry",
    "UnifiedRegistry",
    "PluginManager",
    "PluginDiscovery",
    "tool",
    "resource",
    "prompt",
    "PluginDecorator",
    "create_plugin_decorator",
    "get_tool_decorator",
    "get_resource_decorator",
    "get_prompt_decorator",
]