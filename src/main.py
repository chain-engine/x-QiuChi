#!/usr/bin/env python3
"""
秋池（QiuChi）

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
    >>> from src.main import create_server, tool, resource, prompt
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

import argparse
import sys

from src.core.config import PACKAGE_VERSION, settings
from src.core.logger import setup_logging
from src.core.middleware import (
    ErrorHandlerMiddleware,
    LoggingMiddleware,
    Middleware,
    MiddlewareChain,
)
from src.plugins import PluginMetadata, prompt, resource, tool
from src.server import MCPServer, create_server
from src.transport import TransportConfig, TransportType

__all__ = [
    # 核心类
    "MCPServer",
    "create_server",
    "settings",
    # 插件系统
    "PluginMetadata",
    # 中间件
    "Middleware",
    "MiddlewareChain",
    "ErrorHandlerMiddleware",
    "LoggingMiddleware",
    # 传输层
    "TransportType",
    "TransportConfig",
    # 装饰器
    "tool",
    "resource",
    "prompt",
]

__version__ = PACKAGE_VERSION
__author__ = "John Young <john.young@foxmail.com>"
__description__ = "QiuChi (秋池) - an enterprise-grade MCP server framework"


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="QiuChi - Enterprise-grade MCP Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    # 启动 HTTP 服务器（默认端口 8888）
  %(prog)s --transport stdio  # 启动 Stdio 服务器
  %(prog)s --port 8080        # 在端口 8080 上启动
        """,
    )

    # 服务器配置
    parser.add_argument(
        "--name",
        default=settings.mcp.server_name,
        help=f"服务器名称（默认: {settings.mcp.server_name}）",
    )
    parser.add_argument(
        "--version",
        default=settings.mcp.version,
        help=f"服务器版本（默认: {settings.mcp.version}）",
    )

    # 传输配置
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default=settings.mcp.transport,
        help=f"传输类型（默认: {settings.mcp.transport}）",
    )
    parser.add_argument(
        "--host", default=settings.mcp.host, help=f"HTTP 监听地址（默认: {settings.mcp.host}）"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=settings.mcp.port,
        help=f"HTTP 监听端口（默认: {settings.mcp.port}）",
    )

    # 日志配置
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default=settings.logging.level,
        help=f"日志级别（默认: {settings.logging.level}）",
    )
    parser.add_argument(
        "--log-file",
        default=settings.logging.file_path,
        help=f"日志文件路径（默认: {settings.logging.file_path}）",
    )

    return parser.parse_args()


def update_settings_from_args(args):
    """根据命令行参数更新配置"""
    # 更新传输配置
    settings.mcp.transport = args.transport
    settings.mcp.host = args.host
    settings.mcp.port = args.port
    settings.mcp.server_name = args.name
    settings.mcp.version = args.version

    # 更新日志配置
    settings.logging.level = args.log_level
    settings.logging.file_path = args.log_file


def print_startup_info(server, args):
    """打印启动信息"""
    from src.core.logger import get_logger

    logger = get_logger("main")

    logger.info("=" * 60)
    logger.info(f"QiuChi Server v{settings.mcp.version}")
    logger.info("=" * 60)
    logger.info(f"Server: {settings.mcp.server_name}")
    logger.info(f"Transport: {settings.mcp.transport}")

    if settings.mcp.transport in ["sse", "streamable-http"]:
        logger.info(f"Listening: http://{settings.mcp.host}:{settings.mcp.port}")

    logger.info(f"Features: Middleware={settings.features.middleware}")
    logger.info(f"Log level: {settings.logging.level}")
    logger.info(f"Config file: {settings._config_file}")
    logger.info("=" * 60)


def main_async():
    """主函数"""
    # 解析参数
    args = parse_arguments()

    # 更新配置
    update_settings_from_args(args)

    # 设置日志
    setup_logging()

    # 创建服务器（插件将通过自动发现机制加载）
    server = create_server(
        name=settings.mcp.server_name,
        version=settings.mcp.version,
    )

    # 打印启动信息
    print_startup_info(server, args)

    # 启动服务器
    server.run(
        transport=settings.mcp.transport,
        host=settings.mcp.host,
        port=settings.mcp.port,
    )


def main():
    """主函数"""
    try:
        main_async()
    except KeyboardInterrupt:
        from src.core.logger import get_logger

        logger = get_logger("main")
        logger.info("Server stopped by user")
        sys.exit(0)
    except Exception as e:
        from src.core.logger import get_logger

        logger = get_logger("main")
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
