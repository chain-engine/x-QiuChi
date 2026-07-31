"""
QiuChi 核心插件包基础定义

提供插件类型、状态、元数据以及依赖关系相关的数据结构。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class PluginType(str, Enum):
    """插件类型枚举"""

    TOOL = "tool"
    RESOURCE = "resource"
    PROMPT = "prompt"


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
    dependencies: List[str] = field(default_factory=list)
    config_schema: Optional[Dict[str, Any]] = None


@dataclass
class PluginDependency:
    """插件依赖声明"""

    plugin_name: str
    version_spec: str = "*"  # 支持语义化版本表达式，例如 ">=1.0.0"
    optional: bool = False


__all__ = ["PluginType", "PluginStatus", "PluginMetadata", "PluginDependency"]
