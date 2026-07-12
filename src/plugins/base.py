"""
QiuChi 插件基础定义

包含插件系统的核心枚举和元数据定义。
"""

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
