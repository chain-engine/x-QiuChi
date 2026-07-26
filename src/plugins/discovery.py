"""
QiuChi 插件发现器

提供插件自动发现功能，封装为 PluginDiscovery 类。

发现流程：
    1. 扫描配置的发现路径
    2. 导入模块触发装饰器收集
    3. 返回发现的插件名称列表
"""

import importlib
from pathlib import Path
from typing import Any, List

from core.config.config import settings
from core.logging.logger import get_logger

logger = get_logger(__name__)


class PluginDiscovery:
    """插件发现器"""

    def __init__(self):
        self._discovered_items: List[str] = []

    def discover(self) -> List[str]:
        """
        自动发现插件

        扫描配置的发现路径，导入模块触发装饰器收集。

        Returns:
            发现的插件名称列表
        """
        self._discovered_items.clear()

        for discovery_path in settings.plugins.discovery_paths:
            try:
                module = importlib.import_module(discovery_path)
                module_path = Path(module.__file__).parent if module.__file__ else None

                if module_path:
                    self._discovered_items.extend(self._scan_module(module, module_path))
            except ImportError as e:
                logger.warning(f"无法导入发现路径 {discovery_path}: {e}")

        logger.info(f"发现 {len(self._discovered_items)} 个插件项: {self._discovered_items}")
        return self._discovered_items.copy()

    def _scan_module(self, module: Any, module_path: Path) -> List[str]:
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

    def get_discovered_items(self) -> List[str]:
        """获取所有已发现的插件项"""
        return self._discovered_items.copy()

    def clear(self) -> None:
        """清空已发现的插件"""
        self._discovered_items.clear()


def discover_plugins() -> List[str]:
    """
    便捷函数：发现插件

    Returns:
        发现的插件名称列表
    """
    discovery = PluginDiscovery()
    return discovery.discover()


def create_discovery() -> PluginDiscovery:
    """创建插件发现器实例"""
    return PluginDiscovery()
