"""
QiuChi 插件系统

提供统一的插件管理框架，支持三步流程：
- 发现（PluginDiscovery）：扫描目录，导入模块触发收集
- 收集（PluginCollector）：装饰器将函数收集到全局 Collector
- 注册（PluginRegistry）：从 Collector 读取并注册到注册表

注册流程：
    1. 使用 @tool/@resource/@prompt 装饰器标记函数
    2. PluginDiscovery.discover() 扫描目录，导入模块触发装饰器收集到 Collector 中
    3. 从 Collector 读取并注册到 PluginRegistry
"""

from .base import PluginType, PluginMetadata, PluginStatus
from .collector import (
    tool, resource, prompt,
    get_tool_collector, get_resource_collector, get_prompt_collector,
    PluginCollector,
)
from .registry import PluginRegistry, RegistryItemType, global_registry
from .discovery import PluginDiscovery, discover_plugins, create_discovery

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
    "RegistryItemType",
    "global_registry",
    "PluginDiscovery",
    "discover_plugins",
    "create_discovery",
]
