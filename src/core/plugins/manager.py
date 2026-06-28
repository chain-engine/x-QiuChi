"""
QiuChi 插件管理器

管理插件的加载、启用、禁用和卸载，支持：
- 插件依赖解析
- 生命周期管理
- 配置管理
- 错误隔离
"""

from typing import Dict, List, Optional, Set, Type, Any, TYPE_CHECKING
from pathlib import Path
import importlib
import sys

from .base import Plugin, PluginType, PluginMetadata, PluginStatus
from .registry import PluginRegistry, UnifiedRegistry, RegistryItemType
from ..config.config import settings
from ..logging.logger import get_logger

if TYPE_CHECKING:
    from ..server.server import MCPServer

logger = get_logger(__name__)


class PluginManager:
    """
    插件管理器

    负责插件的全生命周期管理。
    """

    def __init__(self, server: Optional["MCPServer"] = None):
        """
        初始化插件管理器

        Args:
            server: MCP 服务器实例（可选）
        """
        self.server = server
        self.plugins: Dict[str, Plugin] = {}
        self.registry = PluginRegistry("PluginManager")
        self._dependencies: Dict[str, Set[str]] = {}  # 插件依赖图
        self._initialized = False

        logger.debug("PluginManager initialized")

    async def initialize(self) -> None:
        """初始化插件管理器"""
        if self._initialized:
            return

        logger.info("Initializing PluginManager...")

        # 自动发现插件
        if settings.plugins.auto_discovery:
            await self.discover_plugins()

        # 加载启用的插件
        await self.load_enabled_plugins()

        self._initialized = True
        logger.info(f"PluginManager initialized with {len(self.plugins)} plugins")

    async def discover_plugins(self) -> List[str]:
        """
        自动发现插件

        Returns:
            发现的插件名称列表
        """
        discovered = []

        for discovery_path in settings.plugins.discovery_paths:
            try:
                # 尝试导入发现路径
                module = importlib.import_module(discovery_path)
                module_path = Path(module.__file__).parent if module.__file__ else None

                if module_path:
                    # 扫描模块中的插件
                    discovered.extend(await self._scan_module_for_plugins(module, module_path))
            except ImportError as e:
                logger.warning(f"Failed to import discovery path {discovery_path}: {e}")

        logger.info(f"Discovered {len(discovered)} plugins: {discovered}")
        return discovered

    async def _scan_module_for_plugins(self, module: Any, module_path: Path) -> List[str]:
        """扫描模块中的插件（递归扫描子目录）"""
        discovered = []

        # 递归扫描所有 .py 文件
        for py_file in module_path.rglob("*.py"):
            if py_file.name.startswith("_"):
                continue

            # 计算相对路径，构建模块名
            relative_path = py_file.relative_to(module_path)
            module_name_parts = list(relative_path.parts[:-1])  # 移除文件名
            if module_name_parts:
                module_name = f"{module.__name__}.{'.'.join(module_name_parts)}.{py_file.stem}"
            else:
                module_name = f"{module.__name__}.{py_file.stem}"

            try:
                submodule = importlib.import_module(module_name)

                # 查找插件类
                for attr_name in dir(submodule):
                    attr = getattr(submodule, attr_name)

                    # 检查是否是插件类
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, Plugin)
                        and attr != Plugin
                    ):
                        plugin_name = getattr(attr, "__name__", attr_name)
                        discovered.append(plugin_name)

                        # 注册插件类
                        self.register_plugin_class(plugin_name, attr)

                    # 检查是否是装饰器注册的函数
                    elif hasattr(attr, "_is_plugin_item") and attr._is_plugin_item:
                        plugin_name = getattr(attr, "_plugin_name", attr.__name__)
                        discovered.append(plugin_name)

                        # 注册装饰器函数
                        # 注意：装饰器注册的函数在导入时已经自动注册到 MCPServer，
                        # 这里只是记录发现，避免重复注册
                        logger.debug(f"Found decorator-registered function: {plugin_name}")

            except ImportError as e:
                logger.debug(f"Failed to import submodule {module_name}: {e}")

        return discovered

    def register_plugin_class(self, name: str, plugin_class: Type[Plugin]) -> bool:
        """
        注册插件类

        Args:
            name: 插件名称
            plugin_class: 插件类

        Returns:
            是否注册成功
        """
        if name in self.plugins:
            logger.warning(f"Plugin '{name}' already registered")
            return False

        # 创建插件实例
        try:
            # 从类获取元数据
            metadata = getattr(plugin_class, "metadata", PluginMetadata(name=name))
            plugin = plugin_class(metadata)

            self.plugins[name] = plugin
            logger.debug(f"Registered plugin class: {name}")
            return True
        except Exception as e:
            logger.error(f"Failed to register plugin class {name}: {e}")
            return False

    async def register_plugin(self, plugin: Plugin) -> bool:
        """
        注册插件实例

        Args:
            plugin: 插件实例

        Returns:
            是否注册成功
        """
        if plugin.name in self.plugins:
            logger.warning(f"Plugin '{plugin.name}' already registered")
            return False

        self.plugins[plugin.name] = plugin

        # 记录依赖关系
        if plugin.metadata.dependencies:
            self._dependencies[plugin.name] = set(plugin.metadata.dependencies)

        logger.debug(f"Registered plugin: {plugin.name}")
        return True

    async def load_enabled_plugins(self) -> List[str]:
        """
        加载所有启用的插件

        Returns:
            成功加载的插件列表
        """
        loaded = []

        # 获取启用的插件列表
        enabled_plugins = settings.plugins.enabled_plugins
        disabled_plugins = set(settings.plugins.disabled_plugins)

        for plugin_name, plugin in self.plugins.items():
            # 检查是否启用
            if enabled_plugins and plugin_name not in enabled_plugins:
                continue
            if plugin_name in disabled_plugins:
                continue

            # 加载插件
            if await self.load_plugin(plugin_name):
                loaded.append(plugin_name)

        logger.info(f"Loaded {len(loaded)} plugins: {loaded}")
        return loaded

    async def load_plugin(self, plugin_name: str) -> bool:
        """
        加载插件

        Args:
            plugin_name: 插件名称

        Returns:
            是否加载成功
        """
        if plugin_name not in self.plugins:
            logger.error(f"Plugin '{plugin_name}' not found")
            return False

        plugin = self.plugins[plugin_name]

        # 检查依赖
        missing_deps = []
        if plugin_name in self._dependencies:
            for dep in self._dependencies[plugin_name]:
                if dep not in self.plugins or not self.plugins[dep].is_loaded():
                    missing_deps.append(dep)

        if missing_deps:
            logger.error(f"Plugin '{plugin_name}' missing dependencies: {missing_deps}")
            return False

        try:
            # 调用插件生命周期方法
            await plugin.on_load(settings)
            plugin.set_status(PluginStatus.LOADED)

            # 注册插件提供的工具/资源/提示词
            await self._register_plugin_items(plugin)

            logger.info(f"Loaded plugin: {plugin_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to load plugin '{plugin_name}': {e}")
            plugin.set_status(PluginStatus.ERROR)
            return False

    async def _register_plugin_items(self, plugin: Plugin) -> None:
        """注册插件提供的所有项目"""
        from .base import ToolPlugin, ResourcePlugin, PromptPlugin, CompositePlugin

        if isinstance(plugin, ToolPlugin):
            tools = plugin.get_tools()
            for tool_name, tool_func in tools.items():
                self.registry.register(
                    name=tool_name,
                    item=tool_func,
                    item_type=RegistryItemType.TOOL,
                    metadata=plugin.metadata,
                    category=plugin.metadata.category,
                    subcategory=plugin.metadata.subcategory,
                    tags=list(plugin.metadata.tags),
                )

        elif isinstance(plugin, ResourcePlugin):
            resources = plugin.get_resources()
            for resource_name, resource_func in resources.items():
                self.registry.register(
                    name=resource_name,
                    item=resource_func,
                    item_type=RegistryItemType.RESOURCE,
                    metadata=plugin.metadata,
                    category=plugin.metadata.category,
                    subcategory=plugin.metadata.subcategory,
                    tags=list(plugin.metadata.tags),
                )

        elif isinstance(plugin, PromptPlugin):
            prompts = plugin.get_prompts()
            for prompt_name, prompt_func in prompts.items():
                self.registry.register(
                    name=prompt_name,
                    item=prompt_func,
                    item_type=RegistryItemType.PROMPT,
                    metadata=plugin.metadata,
                    category=plugin.metadata.category,
                    subcategory=plugin.metadata.subcategory,
                    tags=list(plugin.metadata.tags),
                )

        elif isinstance(plugin, CompositePlugin):
            # 注册所有类型的项目
            tools = plugin.get_tools()
            for tool_name, tool_func in tools.items():
                self.registry.register(
                    name=tool_name,
                    item=tool_func,
                    item_type=RegistryItemType.TOOL,
                    metadata=plugin.metadata,
                    category=plugin.metadata.category,
                    subcategory=plugin.metadata.subcategory,
                    tags=list(plugin.metadata.tags),
                )

            resources = plugin.get_resources()
            for resource_name, resource_func in resources.items():
                self.registry.register(
                    name=resource_name,
                    item=resource_func,
                    item_type=RegistryItemType.RESOURCE,
                    metadata=plugin.metadata,
                    category=plugin.metadata.category,
                    subcategory=plugin.metadata.subcategory,
                    tags=list(plugin.metadata.tags),
                )

            prompts = plugin.get_prompts()
            for prompt_name, prompt_func in prompts.items():
                self.registry.register(
                    name=prompt_name,
                    item=prompt_func,
                    item_type=RegistryItemType.PROMPT,
                    metadata=plugin.metadata,
                    category=plugin.metadata.category,
                    subcategory=plugin.metadata.subcategory,
                    tags=list(plugin.metadata.tags),
                )

    async def enable_plugin(self, plugin_name: str) -> bool:
        """
        启用插件

        Args:
            plugin_name: 插件名称

        Returns:
            是否启用成功
        """
        if plugin_name not in self.plugins:
            return False

        plugin = self.plugins[plugin_name]
        if plugin.status != PluginStatus.LOADED:
            logger.warning(f"Cannot enable plugin '{plugin_name}' (status: {plugin.status})")
            return False

        try:
            await plugin.on_enable()
            plugin.set_status(PluginStatus.ENABLED)

            # 启用注册表中的项目
            self.registry.enable(plugin_name)

            logger.info(f"Enabled plugin: {plugin_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to enable plugin '{plugin_name}': {e}")
            return False

    async def disable_plugin(self, plugin_name: str) -> bool:
        """
        禁用插件

        Args:
            plugin_name: 插件名称

        Returns:
            是否禁用成功
        """
        if plugin_name not in self.plugins:
            return False

        plugin = self.plugins[plugin_name]
        if plugin.status != PluginStatus.ENABLED:
            return True  # 已经禁用

        try:
            await plugin.on_disable()
            plugin.set_status(PluginStatus.DISABLED)

            # 禁用注册表中的项目
            self.registry.disable(plugin_name)

            logger.info(f"Disabled plugin: {plugin_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to disable plugin '{plugin_name}': {e}")
            return False

    async def unload_plugin(self, plugin_name: str) -> bool:
        """
        卸载插件

        Args:
            plugin_name: 插件名称

        Returns:
            是否卸载成功
        """
        if plugin_name not in self.plugins:
            return False

        plugin = self.plugins[plugin_name]

        try:
            # 先禁用
            if plugin.is_enabled():
                await self.disable_plugin(plugin_name)

            # 卸载
            await plugin.on_unload()
            plugin.set_status(PluginStatus.UNLOADED)

            # 从注册表移除项目
            self.registry.unregister(plugin_name)

            logger.info(f"Unloaded plugin: {plugin_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to unload plugin '{plugin_name}': {e}")
            return False

    def get_plugin(self, plugin_name: str) -> Optional[Plugin]:
        """获取插件"""
        return self.plugins.get(plugin_name)

    def get_plugins(
        self,
        plugin_type: Optional[PluginType] = None,
        category: Optional[str] = None,
        enabled_only: bool = True,
    ) -> List[Plugin]:
        """
        获取插件列表

        Args:
            plugin_type: 按类型过滤
            category: 按分类过滤
            enabled_only: 是否只返回启用的插件

        Returns:
            插件列表
        """
        plugins = []
        for plugin in self.plugins.values():
            if enabled_only and not plugin.is_enabled():
                continue
            if plugin_type and plugin.type != plugin_type:
                continue
            if category and plugin.metadata.category != category:
                continue
            plugins.append(plugin)
        return plugins

    def get_plugin_info(self, plugin_name: str) -> Optional[Dict[str, Any]]:
        """获取插件信息"""
        plugin = self.get_plugin(plugin_name)
        return plugin.get_info() if plugin else None

    async def shutdown(self) -> None:
        """关闭插件管理器"""
        logger.info("Shutting down PluginManager...")

        # 卸载所有插件
        for plugin_name in list(self.plugins.keys()):
            await self.unload_plugin(plugin_name)

        self.plugins.clear()
        self._dependencies.clear()
        self._initialized = False

        logger.info("PluginManager shutdown complete")