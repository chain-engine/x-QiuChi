"""
核心模块

提供核心配置、中间件、日志、插件等基础能力。
"""

from core.config import settings, Settings
from core.logger import get_logger, setup_logging
from core.middleware import (
    Middleware,
    MiddlewareChain,
    ErrorHandlerMiddleware,
    LoggingMiddleware,
    MCPAuthMiddleware,
    CacheMiddleware,
)
from plugins import PluginManager, PluginType, PluginMetadata, PluginStatus

__all__ = [
    "settings",
    "Settings",
    "Middleware",
    "MiddlewareChain",
    "ErrorHandlerMiddleware",
    "LoggingMiddleware",
    "MCPAuthMiddleware",
    "CacheMiddleware",
    "get_logger",
    "setup_logging",
    "PluginManager",
    "PluginType",
    "PluginMetadata",
    "PluginStatus",
]
