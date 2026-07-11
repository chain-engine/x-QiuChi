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
from typing import Any, Dict, List, Optional, Type, TYPE_CHECKING
from pathlib import Path

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