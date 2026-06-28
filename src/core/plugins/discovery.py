"""
QiuChi 插件发现模块

提供插件的自动发现和加载功能。
"""

import importlib
import inspect
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from .base import Plugin, PluginMetadata, PluginType
from ..logging.logger import get_logger

logger = get_logger(__name__)


class PluginDiscovery:
    """
    插件发现器

    自动扫描指定路径，发现并加载插件。
    """

    def __init__(self):
        self.discovered_plugins: Dict[str, Type[Plugin]] = {}

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
            logger.warning(f"Plugin discovery path does not exist: {path}")
            return discovered

        # 扫描Python文件
        for py_file in path.glob("*.py"):
            if py_file.name.startswith("_"):
                continue

            module_name = f"{base_package}.{py_file.stem}" if base_package else py_file.stem
            discovered.extend(self._discover_in_module(module_name))

        # 扫描子目录（包）
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

            # 查找插件类
            for attr_name in dir(module):
                attr = getattr(module, attr_name)

                # 检查是否是插件类
                if (
                    inspect.isclass(attr)
                    and issubclass(attr, Plugin)
                    and attr != Plugin
                    and attr.__module__ == module_name
                ):
                    plugin_name = getattr(attr, "__plugin_name__", attr.__name__)
                    self.discovered_plugins[plugin_name] = attr
                    discovered.append(plugin_name)
                    logger.debug(f"Discovered plugin class: {plugin_name} in {module_name}")

                # 检查是否是装饰器注册的函数
                elif callable(attr) and hasattr(attr, "_is_plugin_item"):
                    plugin_name = getattr(attr, "_plugin_name", attr.__name__)
                    # 为装饰器注册的函数创建虚拟插件类
                    # 这里简化处理，实际注册在装饰器中完成
                    discovered.append(plugin_name)
                    logger.debug(f"Discovered plugin function: {plugin_name} in {module_name}")

        except ImportError as e:
            logger.warning(f"Failed to import module {module_name}: {e}")
        except Exception as e:
            logger.error(f"Error discovering plugins in {module_name}: {e}")

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
                logger.warning(f"Cannot find package path: {package_name}")
                return []
        except ImportError as e:
            logger.warning(f"Failed to import package {package_name}: {e}")
            return []

    def get_discovered_plugins(self) -> Dict[str, Type[Plugin]]:
        """
        获取所有已发现的插件

        Returns:
            插件名称到插件类的映射
        """
        return self.discovered_plugins.copy()

    def clear(self) -> None:
        """清空已发现的插件"""
        self.discovered_plugins.clear()


def discover_plugins(paths: List[str]) -> Dict[str, Type[Plugin]]:
    """
    便捷函数：从多个路径发现插件

    Args:
        paths: 要扫描的路径列表

    Returns:
        发现的插件字典
    """
    discovery = PluginDiscovery()

    for path_str in paths:
        path = Path(path_str)
        if path.exists():
            discovery.discover_from_path(path)
        else:
            # 尝试作为包名导入
            discovery.discover_from_package(path_str)

    return discovery.get_discovered_plugins()


__all__ = ["PluginDiscovery", "discover_plugins"]