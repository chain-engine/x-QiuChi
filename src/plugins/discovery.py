"""
QiuChi 插件发现模块

提供装饰器注册函数的自动发现功能。
"""

import importlib
from pathlib import Path
from typing import Any, List

from core.logging.logger import get_logger

logger = get_logger(__name__)


class PluginDiscovery:
    """
    插件发现器

    自动扫描指定路径，发现装饰器注册的函数。
    """

    def __init__(self):
        self.discovered_items: List[str] = []

    def discover_from_path(self, path: Path, base_package: str = "") -> List[str]:
        """
        从路径发现插件

        Args:
            path: 要扫描的路径
            base_package: 基础包名

        Returns:
            发现的插件名称列表
        """
        discovered = []

        if not path.exists():
            logger.warning(f"插件发现路径不存在: {path}")
            return discovered

        for py_file in path.glob("*.py"):
            if py_file.name.startswith("_"):
                continue

            module_name = f"{base_package}.{py_file.stem}" if base_package else py_file.stem
            discovered.extend(self._discover_in_module(module_name))

        for subdir in path.iterdir():
            if subdir.is_dir() and not subdir.name.startswith("_"):
                init_file = subdir / "__init__.py"
                if init_file.exists():
                    package_name = f"{base_package}.{subdir.name}" if base_package else subdir.name
                    discovered.extend(self.discover_from_path(subdir, package_name))

        return discovered

    def _discover_in_module(self, module_name: str) -> List[str]:
        """
        在模块中发现插件

        Args:
            module_name: 模块名

        Returns:
            发现的插件名称列表
        """
        discovered = []

        try:
            module = importlib.import_module(module_name)

            for attr_name in dir(module):
                attr = getattr(module, attr_name)

                if callable(attr) and hasattr(attr, "_is_plugin_item"):
                    plugin_name = getattr(attr, "_plugin_name", attr.__name__)
                    self.discovered_items.append(plugin_name)
                    discovered.append(plugin_name)
                    logger.debug(f"发现插件函数: {plugin_name} in {module_name}")

        except ImportError as e:
            logger.warning(f"无法导入模块 {module_name}: {e}")
        except Exception as e:
            logger.error(f"发现插件时出错 {module_name}: {e}")

        return discovered

    def discover_from_package(self, package_name: str) -> List[str]:
        """
        从包发现插件

        Args:
            package_name: 包名

        Returns:
            发现的插件名称列表
        """
        try:
            package = importlib.import_module(package_name)
            package_path = Path(package.__file__).parent if package.__file__ else None

            if package_path:
                return self.discover_from_path(package_path, package_name)
            else:
                logger.warning(f"无法找到包路径: {package_name}")
                return []
        except ImportError as e:
            logger.warning(f"无法导入包 {package_name}: {e}")
            return []

    def get_discovered_items(self) -> List[str]:
        """获取所有已发现的插件项"""
        return self.discovered_items.copy()

    def clear(self) -> None:
        """清空已发现的插件"""
        self.discovered_items.clear()


def discover_plugins(paths: List[str]) -> List[str]:
    """
    便捷函数：从多个路径发现插件

    Args:
        paths: 要扫描的路径列表

    Returns:
        发现的插件名称列表
    """
    discovery = PluginDiscovery()

    for path_str in paths:
        path = Path(path_str)
        if path.exists():
            discovery.discover_from_path(path)
        else:
            discovery.discover_from_package(path_str)

    return discovery.get_discovered_items()


__all__ = ["PluginDiscovery", "discover_plugins"]
