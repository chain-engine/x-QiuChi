"""
QiuChi 插件系统

提供统一的插件管理框架，支持：
- 装饰器注册（@tool, @resource, @prompt）
- 插件发现（discover_plugins）
- 统一注册表（PluginRegistry）

注册流程：
    1. 使用 @tool/@resource/@prompt 装饰器标记函数
    2. discover_plugins() 扫描目录，导入模块触发装饰器收集
    3. register_from_collectors() 从收集器读取并注册到注册表
"""

import importlib
from pathlib import Path
from typing import Any, List

from .base import PluginType, PluginMetadata, PluginStatus
from .decorators import (
    tool, resource, prompt,
    get_tool_collector, get_resource_collector, get_prompt_collector,
    PluginCollector,
)
from .registry import PluginRegistry, RegistryItemType, global_registry
from core.logging.logger import get_logger

logger = get_logger(__name__)


def discover_plugins() -> List[str]:
    """
    自动发现插件

    扫描配置的发现路径，导入模块触发装饰器收集。

    Returns:
        发现的插件名称列表
    """
    from core.config.config import settings

    discovered = []

    for discovery_path in settings.plugins.discovery_paths:
        try:
            module = importlib.import_module(discovery_path)
            module_path = Path(module.__file__).parent if module.__file__ else None

            if module_path:
                discovered.extend(_scan_module(module, module_path))
        except ImportError as e:
            logger.warning(f"无法导入发现路径 {discovery_path}: {e}")

    logger.info(f"发现 {len(discovered)} 个插件项: {discovered}")
    return discovered


def _scan_module(module: Any, module_path: Path) -> List[str]:
    """扫描模块中的插件"""
    discovered = []

    for py_file in module_path.rglob("*.py"):
        if py_file.name.startswith("_"):
            continue

        relative_path = py_file.relative_to(module_path)
        module_name_parts = list(relative_path.parts[:-1])
        if module_name_parts:
            module_name = f"{module.__name__}.{'.'.join(module_name_parts)}.{py_file.stem}"
        else:
            module_name = f"{module.__name__}.{py_file.stem}"

        try:
            submodule = importlib.import_module(module_name)

            for attr_name in dir(submodule):
                attr = getattr(submodule, attr_name)

                if hasattr(attr, "_is_plugin_item") and attr._is_plugin_item:
                    plugin_name = getattr(attr, "_plugin_name", attr.__name__)
                    discovered.append(plugin_name)
                    logger.debug(f"发现装饰器注册的函数: {plugin_name}")

        except ImportError as e:
            logger.debug(f"无法导入子模块 {module_name}: {e}")

    return discovered


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
    "discover_plugins",
]
