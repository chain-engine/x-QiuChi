"""
QiuChi 核心插件包

提供 plugins（装饰器层）之上的高级插件管理能力：
- PluginManager：自动发现、依赖解析、生命周期管理
- PluginLoader：基于插件类的加载器（区别于基于装饰器的轻量级插件）
"""

from .base import PluginType, PluginMetadata, PluginStatus
from .manager import PluginManager
from .loader import PluginLoader

__all__ = [
    "PluginType",
    "PluginMetadata",
    "PluginStatus",
    "PluginManager",
    "PluginLoader",
]
