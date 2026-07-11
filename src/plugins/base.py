"""
QiuChi 插件基类

定义插件的标准接口和生命周期，支持：
- 工具（Tools）、资源（Resources）、提示词（Prompts）插件
- 统一的生命周期管理
- 依赖声明和解析
- 配置注入
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, TYPE_CHECKING
from pathlib import Path

T = TypeVar("T")
FuncType = Callable[..., Any]

if TYPE_CHECKING:
    from core.config.config import Settings


class PluginType(str, Enum):
    """插件类型枚举"""
    TOOL = "tool"
    RESOURCE = "resource"
    PROMPT = "prompt"
    COMPOSITE = "composite"  # 包含多种类型的插件


class PluginStatus(str, Enum):
    """插件状态枚举"""
    UNLOADED = "unloaded"
    LOADED = "loaded"
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"


@dataclass
class PluginMetadata:
    """插件元数据"""
    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    license: str = "MIT"
    type: PluginType = PluginType.TOOL
    category: str = "default"
    subcategory: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)  # 依赖的其他插件
    config_schema: Optional[Dict[str, Any]] = None  # 配置模式


class Plugin(ABC):
    """
    插件基类

    所有 QiuChi 插件必须继承此类，实现标准接口。
    """

    def __init__(self, metadata: PluginMetadata):
        self.metadata = metadata
        self.status: PluginStatus = PluginStatus.UNLOADED
        self.config: Dict[str, Any] = {}
        self._initialized: bool = False

    @property
    def name(self) -> str:
        """插件名称"""
        return self.metadata.name

    @property
    def type(self) -> PluginType:
        """插件类型"""
        return self.metadata.type

    # 生命周期方法
    @abstractmethod
    async def on_load(self, settings: "Settings") -> None:
        """
        插件加载时调用

        Args:
            settings: 全局配置
        """
        pass

    @abstractmethod
    async def on_enable(self) -> None:
        """插件启用时调用"""
        pass

    @abstractmethod
    async def on_disable(self) -> None:
        """插件禁用时调用"""
        pass

    @abstractmethod
    async def on_unload(self) -> None:
        """插件卸载时调用"""
        pass

    # 配置管理
    def configure(self, config: Dict[str, Any]) -> None:
        """
        配置插件

        Args:
            config: 插件配置
        """
        self.config.update(config)

    def get_config(self) -> Dict[str, Any]:
        """获取插件配置"""
        return self.config.copy()

    # 状态管理
    def set_status(self, status: PluginStatus) -> None:
        """设置插件状态"""
        self.status = status

    def is_enabled(self) -> bool:
        """检查插件是否启用"""
        return self.status == PluginStatus.ENABLED

    def is_loaded(self) -> bool:
        """检查插件是否已加载"""
        return self.status != PluginStatus.UNLOADED

    # 工具方法
    def get_info(self) -> Dict[str, Any]:
        """获取插件信息"""
        return {
            "name": self.name,
            "version": self.metadata.version,
            "type": self.type.value,
            "status": self.status.value,
            "description": self.metadata.description,
            "category": self.metadata.category,
            "subcategory": self.metadata.subcategory,
            "tags": self.metadata.tags,
            "dependencies": self.metadata.dependencies,
        }


class ToolPlugin(Plugin):
    """工具插件基类"""

    def __init__(self, metadata: PluginMetadata):
        super().__init__(metadata)
        self.metadata.type = PluginType.TOOL
        self._tools: Dict[str, Any] = {}

    @abstractmethod
    def get_tools(self) -> Dict[str, Any]:
        """
        获取插件提供的工具

        Returns:
            工具字典：{工具名称: 工具函数}
        """
        pass


class ResourcePlugin(Plugin):
    """资源插件基类"""

    def __init__(self, metadata: PluginMetadata):
        super().__init__(metadata)
        self.metadata.type = PluginType.RESOURCE
        self._resources: Dict[str, Any] = {}

    @abstractmethod
    def get_resources(self) -> Dict[str, Any]:
        """
        获取插件提供的资源

        Returns:
            资源字典：{资源URI: 资源函数}
        """
        pass


class PromptPlugin(Plugin):
    """提示词插件基类"""

    def __init__(self, metadata: PluginMetadata):
        super().__init__(metadata)
        self.metadata.type = PluginType.PROMPT
        self._prompts: Dict[str, Any] = {}

    @abstractmethod
    def get_prompts(self) -> Dict[str, Any]:
        """
        获取插件提供的提示词

        Returns:
            提示词字典：{提示词名称: 提示词函数}
        """
        pass


class CompositePlugin(Plugin):
    """复合插件基类（同时提供多种类型）"""

    def __init__(self, metadata: PluginMetadata):
        super().__init__(metadata)
        self.metadata.type = PluginType.COMPOSITE
        self._tools: Dict[str, Any] = {}
        self._resources: Dict[str, Any] = {}
        self._prompts: Dict[str, Any] = {}

    @abstractmethod
    def get_tools(self) -> Dict[str, Any]:
        """获取工具"""
        pass

    @abstractmethod
    def get_resources(self) -> Dict[str, Any]:
        """获取资源"""
        pass

    @abstractmethod
    def get_prompts(self) -> Dict[str, Any]:
        """获取提示词"""
        pass


class PluginDecorator:
    """
    插件装饰器基类

    用于创建统一风格的插件装饰器。
    """

    def __init__(self, plugin_type: PluginType):
        self.plugin_type = plugin_type
        self._registered_items: Dict[str, Dict[str, Any]] = {}

    def __call__(
        self,
        name: Optional[str] = None,
        category: str = "default",
        subcategory: Optional[str] = None,
        tags: Optional[list[str]] = None,
        **metadata,
    ) -> Callable[[FuncType], FuncType]:
        """
        创建装饰器

        Args:
            name: 插件项名称
            category: 分类
            subcategory: 子分类
            tags: 标签列表
            **metadata: 额外元数据

        Returns:
            装饰器函数
        """
        def decorator(func: FuncType) -> FuncType:
            func_name = name or func.__name__
            func_doc = func.__doc__ or ""

            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)

            wrapper._is_plugin_item = True
            wrapper._plugin_type = self.plugin_type.value
            wrapper._plugin_name = func_name
            wrapper._plugin_category = category
            wrapper._plugin_subcategory = subcategory
            wrapper._plugin_tags = tags or []
            wrapper._plugin_metadata = metadata
            wrapper._plugin_func = func

            self._registered_items[func_name] = {
                "name": func_name,
                "func": wrapper,
                "type": self.plugin_type,
                "category": category,
                "subcategory": subcategory,
                "tags": tags or [],
                "metadata": metadata,
                "doc": func_doc,
            }

            return wrapper

        return decorator

    def get_registered_items(self) -> Dict[str, Dict[str, Any]]:
        """获取所有已注册的项"""
        return self._registered_items.copy()

    def clear_registered_items(self) -> None:
        """清空已注册的项"""
        self._registered_items.clear()


def create_plugin_decorator(plugin_type: str) -> PluginDecorator:
    """
    创建插件装饰器

    Args:
        plugin_type: 插件类型 ("tool", "resource", "prompt")

    Returns:
        PluginDecorator 实例
    """
    type_map = {
        "tool": PluginType.TOOL,
        "resource": PluginType.RESOURCE,
        "prompt": PluginType.PROMPT,
    }

    if plugin_type not in type_map:
        raise ValueError(f"Invalid plugin type: {plugin_type}. Valid options: {list(type_map.keys())}")

    return PluginDecorator(type_map[plugin_type])


_tool_decorator: Optional[PluginDecorator] = None
_resource_decorator: Optional[PluginDecorator] = None
_prompt_decorator: Optional[PluginDecorator] = None


def get_tool_decorator() -> PluginDecorator:
    """获取工具装饰器实例"""
    global _tool_decorator
    if _tool_decorator is None:
        _tool_decorator = create_plugin_decorator("tool")
    return _tool_decorator


def get_resource_decorator() -> PluginDecorator:
    """获取资源装饰器实例"""
    global _resource_decorator
    if _resource_decorator is None:
        _resource_decorator = create_plugin_decorator("resource")
    return _resource_decorator


def get_prompt_decorator() -> PluginDecorator:
    """获取提示词装饰器实例"""
    global _prompt_decorator
    if _prompt_decorator is None:
        _prompt_decorator = create_plugin_decorator("prompt")
    return _prompt_decorator


def tool(
    name: Optional[str] = None,
    category: str = "default",
    subcategory: Optional[str] = None,
    tags: Optional[list[str]] = None,
    **metadata,
) -> Callable[[FuncType], FuncType]:
    """
    工具装饰器

    Args:
        name: 工具名称
        category: 分类
        subcategory: 子分类
        tags: 标签列表
        **metadata: 额外元数据

    Returns:
        装饰器函数
    """
    return get_tool_decorator()(name, category, subcategory, tags, **metadata)


def resource(
    name: Optional[str] = None,
    category: str = "default",
    subcategory: Optional[str] = None,
    tags: Optional[list[str]] = None,
    **metadata,
) -> Callable[[FuncType], FuncType]:
    """
    资源装饰器

    Args:
        name: 资源名称（通常是 URI）
        category: 分类
        subcategory: 子分类
        tags: 标签列表
        **metadata: 额外元数据

    Returns:
        装饰器函数
    """
    return get_resource_decorator()(name, category, subcategory, tags, **metadata)


def prompt(
    name: Optional[str] = None,
    category: str = "default",
    subcategory: Optional[str] = None,
    tags: Optional[list[str]] = None,
    **metadata,
) -> Callable[[FuncType], FuncType]:
    """
    提示词装饰器

    Args:
        name: 提示词名称
        category: 分类
        subcategory: 子分类
        tags: 标签列表
        **metadata: 额外元数据

    Returns:
        装饰器函数
    """
    return get_prompt_decorator()(name, category, subcategory, tags, **metadata)