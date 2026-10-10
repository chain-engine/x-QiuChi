"""
核心模块

提供核心配置、中间件、日志、插件等基础能力。
"""

from src.core.config import Settings, settings
from src.core.logger import get_logger, setup_logging
from src.core.middleware import (
    CacheMiddleware,
    ErrorHandlerMiddleware,
    LoggingMiddleware,
    MCPAuthMiddleware,
    Middleware,
    MiddlewareChain,
)
from src.plugins import PluginManager, PluginMetadata, PluginStatus, PluginType

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
