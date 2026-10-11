"""
插件基础定义（plugins 包）

包含插件系统的核心元数据定义（枚举统一定义在 src/constants/enums.py）。
"""

from dataclasses import dataclass, field
from typing import Any

from src.constants import PluginStatus, PluginType


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
    subcategory: str | None = None
    tags: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    config_schema: dict[str, Any] | None = None


@dataclass
class PluginDependency:
    """插件依赖声明"""

    plugin_name: str
    version_spec: str = "*"  # 支持语义化版本表达式，例如 ">=1.0.0"
    optional: bool = False


__all__ = ["PluginStatus", "PluginType", "PluginMetadata", "PluginDependency"]
