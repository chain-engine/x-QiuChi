"""
插件系统

提供统一的插件管理框架，支持三步流程：
- 发现（PluginDiscovery）：扫描目录，导入模块触发收集
- 收集（PluginCollector）：装饰器将函数收集到全局 Collector
- 注册（PluginRegistry）：从 Collector 读取并注册到注册表

注册流程：
    1. 使用 @tool/@resource/@prompt 装饰器标记函数
    2. PluginDiscovery.discover() 扫描目录，导入模块触发装饰器收集到 Collector 中
    3. 从 Collector 读取并注册到 PluginRegistry
"""

from .base import PluginType, PluginMetadata, PluginStatus, PluginDependency
from .collector import (
    tool, resource, prompt,
    get_tool_collector, get_resource_collector, get_prompt_collector,
    PluginCollector,
)
from .registry import PluginRegistry, RegistryItemType, global_registry
from .discovery import PluginDiscovery, discover_plugins, create_discovery
from .loader import Plugin, PluginLoader
from .manager import PluginManager

__all__ = [
    # 基础类型
    "PluginType",
    "PluginStatus",
    "PluginMetadata",
    "PluginDependency",
    # 装饰器 & 收集器
    "tool",
    "resource",
    "prompt",
    "get_tool_collector",
    "get_resource_collector",
    "get_prompt_collector",
    "PluginCollector",
    # 注册表
    "PluginRegistry",
    "RegistryItemType",
    "global_registry",
    # 发现
    "PluginDiscovery",
    "discover_plugins",
    "create_discovery",
    # 加载器 & 管理器
    "Plugin",
    "PluginLoader",
    "PluginManager",
]
