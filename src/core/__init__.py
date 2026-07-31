"""
QiuChi 核心模块

提供核心配置、服务器、中间件、传输层、日志、插件等基础能力。
"""

from core.config import settings, Settings
from core.logging import get_logger, setup_logging
from core.middleware import (
    Middleware,
    MiddlewareChain,
    ErrorHandlerMiddleware,
    LoggingMiddleware,
    AuthMiddleware,
    CacheMiddleware,
)
from core.transport import TransportType, TransportConfig, get_transport_config
from core.plugins import PluginManager, PluginType, PluginMetadata, PluginStatus

# core.server 依赖较多模块，延迟导入避免循环
from core.server import MCPServer, LifecycleManager, ServerState, create_server

__all__ = [
    "settings",
    "Settings",
    "MCPServer",
    "LifecycleManager",
    "ServerState",
    "create_server",
    "Middleware",
    "MiddlewareChain",
    "ErrorHandlerMiddleware",
    "LoggingMiddleware",
    "AuthMiddleware",
    "CacheMiddleware",
    "TransportType",
    "TransportConfig",
    "get_transport_config",
    "get_logger",
    "setup_logging",
    "PluginManager",
    "PluginType",
    "PluginMetadata",
    "PluginStatus",
]
