"""
QiuChi (秋池) - 企业级 MCP 服务器框架

一个基于 FastMCP 框架封装的企业级 MCP (Model Context Protocol) 服务器。
提供插件化架构、中间件支持、统一配置等企业级特性。

主要特性:
- 完全遵循 MCP 协议，实现 Tools、Resources、Prompts 三大核心原语
- 插件化设计，支持自动发现和生命周期管理
- 中间件管道，支持认证、缓存、日志、错误处理等
- 统一配置系统，支持环境变量、YAML 文件和热重载
- 多传输层支持 (Stdio/SSE/HTTP)
- 完整的类型提示和文档

快速开始:
    >>> from src import create_server, tool, resource, prompt
    >>> server = create_server("MyServer")
    >>>
    >>> @tool(category="math")
    ... def add(a: float, b: float) -> float:
    ...     '''Add two numbers.'''
    ...     return a + b
    >>>
    >>> server.run()

版本: 0.1.0
许可证: MIT
"""

from .core.server import MCPServer, create_server
from .core.config import settings
from .core.plugins import Plugin, PluginMetadata, PluginType
from .core.middleware import (
    Middleware, MiddlewareChain,
    ErrorHandlerMiddleware, LoggingMiddleware,
    AuthMiddleware, CacheMiddleware,
)
from .core.transport import TransportType, TransportConfig
from .plugins.base import tool, resource, prompt

__all__ = [
    # 核心类
    "MCPServer",
    "create_server",
    "settings",
    # 插件系统
    "Plugin",
    "PluginMetadata",
    "PluginType",
    # 中间件
    "Middleware",
    "MiddlewareChain",
    "ErrorHandlerMiddleware",
    "LoggingMiddleware",
    "AuthMiddleware",
    "CacheMiddleware",
    # 传输层
    "TransportType",
    "TransportConfig",
    # 装饰器
    "tool",
    "resource",
    "prompt",
]

__version__ = "0.1.0"
__author__ = "John Young <john.young@foxmail.com>"
__description__ = "QiuChi (秋池) - an enterprise-grade MCP server framework"