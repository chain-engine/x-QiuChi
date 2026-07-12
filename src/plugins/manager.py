"""
QiuChi 插件管理器

管理插件的全生命周期：发现 → 加载 → 启用 → 禁用 → 卸载

注册机制（两阶段）：
    阶段1：发现与收集
        - 扫描目录，导入模块
        - 装饰器自动收集函数到 Collector

    阶段2：统一注册
        - 从 Collector 读取装饰器注册的函数
        - 统一注册到注册表

配置控制：
    - enabled_plugins: 白名单，空列表表示启用所有
    - disabled_plugins: 黑名单，优先级低于白名单
"""

from typing import Dict, List, Optional, Set, Type, Any, TYPE_CHECKING
from pathlib import Path
import importlib

from .base import PluginType, PluginMetadata, PluginStatus
from .registry import PluginRegistry, UnifiedRegistry, RegistryItemType
from core.config.config import settings
from core.logging.logger import get_logger

if TYPE_CHECKING:
    from core.server.server import MCPServer

logger = get_logger(__name__)


class PluginManager:
    """插件管理器"""

    def __init__(self, server: Optional["MCPServer"] = None):
        self.server = server
        self.registry = PluginRegistry("PluginManager")
        self._discovered_items: Dict[str, Dict[str, Any]] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """初始化插件系统（两阶段注册）"""
        if self._initialized:
            return

        logger.info("=== 开始初始化插件系统 ===")

        # 阶段1：发现与收集
        await self._phase1_discover_and_collect()

        # 阶段2：统一注册
        await self._phase2_register_all_items()

        self._initialized = True
        logger.info("=== 插件系统初始化完成 ===")

    async def _phase1_discover_and_collect(self) -> None:
        """阶段1：发现插件并收集装饰器注册的函数"""
        logger.info("[阶段1] 发现插件并收集装饰器注册的函数...")

        if settings.plugins.auto_discovery:
            discovered = await self.discover_plugins()
            logger.info(f"[阶段1] 发现 {len(discovered)} 个插件项")

    async def _phase2_register_all_items(self) -> None:
        """阶段2：将收集到的所有项统一注册到注册表"""
        logger.info("[阶段2] 统一注册所有插件项...")

        if self.server:
            self.server._register_decorator_functions()

        logger.info("[阶段2] 注册完成")

    async def discover_plugins(self) -> List[str]:
        """自动发现插件"""
        discovered = []

        for discovery_path in settings.plugins.discovery_paths:
            try:
                module = importlib.import_module(discovery_path)
                module_path = Path(module.__file__).parent if module.__file__ else None

                if module_path:
                    discovered.extend(self._scan_module_for_plugins(module, module_path))
            except ImportError as e:
                logger.warning(f"无法导入发现路径 {discovery_path}: {e}")

        logger.info(f"发现 {len(discovered)} 个插件项: {discovered}")
        return discovered

    async def _scan_module_for_plugins(self, module: Any, module_path: Path) -> List[str]:
        """扫描模块中的插件（递归扫描子目录）"""
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

    async def shutdown(self) -> None:
        """关闭插件管理器"""
        logger.info("关闭插件管理器...")

        self._discovered_items.clear()
        self._initialized = False

        logger.info("插件管理器关闭完成")
