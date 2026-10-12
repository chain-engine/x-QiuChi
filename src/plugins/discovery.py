"""
插件发现器（发现组件）

提供插件自动发现功能，封装为 PluginDiscovery 类。

发现流程：
    1. 扫描配置的发现路径
    2. 导入模块触发装饰器收集（@tool/@resource/@prompt → 全局 collector）
    3. 返回发现的插件名称列表
"""

import importlib
from pathlib import Path
from typing import Any

from src.constants import PluginType
from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger(__name__)


class PluginDiscovery:
    """插件发现器（发现组件）

    由 PluginManager 在发现阶段临时创建并调用，扫描完成后即弃，不常驻。
    只负责"扫描 + 导入 + 触发装饰器收集"；不感知 Collector / Registry，
    收集结果由 PluginManager 在注册阶段读取。
    """

    def __init__(self):
        self._discovered_items: list[tuple[str, str]] = []

    def discover(self) -> list[str]:
        """
        自动发现插件（tool / resource / prompt）

        扫描配置的发现路径并导入模块，import 副作用触发
        @tool/@resource/@prompt 收集进全局 collector。

        Returns:
            发现的插件名称列表（不分类型）
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

        self._log_summary()
        return [name for name, _ in self._discovered_items]

    def _scan_module(self, module: Any, module_path: Path) -> list[tuple[str, str]]:
        """扫描模块中的插件，返回 (名称, 类型) 对"""
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
                        plugin_type = getattr(attr, "_plugin_type", "")
                        discovered.append((plugin_name, plugin_type))
                        logger.debug(f"发现插件: [{plugin_type}] {plugin_name}")

            except ImportError as e:
                logger.debug(f"无法导入子模块 {module_name}: {e}")

        return discovered

    def _log_summary(self) -> None:
        """按插件类型分组输出发现结果（固定 tool → resource → prompt 顺序）。"""
        grouped: dict[str, list[str]] = {}
        for name, ptype in self._discovered_items:
            grouped.setdefault(ptype, []).append(name)

        parts = []
        for ptype in PluginType:
            names = grouped.get(ptype.value)
            if names:
                parts.append(f"{ptype.desc}[{len(names)}]: {', '.join(sorted(names))}")

        logger.info(f"发现 {len(self._discovered_items)} 个插件 | {' | '.join(parts)}")


def discover_plugins() -> list[str]:
    """
    便捷函数：发现插件（等价于 PluginDiscovery().discover()）

    Returns:
        发现的插件名称列表
    """
    discovery = PluginDiscovery()
    return discovery.discover()
