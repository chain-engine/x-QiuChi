#!/usr/bin/env python3
"""
QiuChi 服务器主入口

企业级 MCP 服务器框架的启动入口。
支持命令行参数和环境变量配置。

Usage:
    # 启动 HTTP 服务器（默认）
    python main.py

    # 启动 Stdio 服务器（Claude Desktop 兼容）
    python main.py --transport stdio

    # 自定义端口
    python main.py --port 8080 --host 127.0.0.1

    # 使用配置文件
    python main.py --config custom_config.yaml
"""

import argparse
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src import create_server, settings
from src.core.logging.logger import setup_logging


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="QiuChi - Enterprise-grade MCP Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    # 启动 HTTP 服务器（默认端口 8000）
  %(prog)s --transport stdio  # 启动 Stdio 服务器
  %(prog)s --port 8080        # 在端口 8080 上启动
  %(prog)s --config custom.yaml  # 使用自定义配置文件
        """
    )

    # 服务器配置
    parser.add_argument(
        "--name",
        default=settings.mcp.server_name,
        help=f"服务器名称（默认: {settings.mcp.server_name}）"
    )
    parser.add_argument(
        "--version",
        default=settings.mcp.version,
        help=f"服务器版本（默认: {settings.mcp.version}）"
    )

    # 传输配置
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default=settings.mcp.transport.value,
        help=f"传输类型（默认: {settings.mcp.transport.value}）"
    )
    parser.add_argument(
        "--host",
        default=settings.mcp.host,
        help=f"HTTP 监听地址（默认: {settings.mcp.host}）"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=settings.mcp.port,
        help=f"HTTP 监听端口（默认: {settings.mcp.port}）"
    )

    # 配置文件
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="配置文件路径（默认: config.yaml）"
    )

    # 日志配置
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default=settings.logging.level.value,
        help=f"日志级别（默认: {settings.logging.level.value}）"
    )
    parser.add_argument(
        "--log-file",
        default=settings.logging.file_path,
        help=f"日志文件路径（默认: {settings.logging.file_path}）"
    )

    # 功能开关
    parser.add_argument(
        "--no-tools",
        action="store_true",
        help="禁用 Tools 原语"
    )
    parser.add_argument(
        "--no-resources",
        action="store_true",
        help="禁用 Resources 原语"
    )
    parser.add_argument(
        "--no-prompts",
        action="store_true",
        help="禁用 Prompts 原语"
    )

    return parser.parse_args()


def update_settings_from_args(args):
    """根据命令行参数更新配置"""
    # 更新传输配置
    from src.core.transport.transport import TransportType
    settings.mcp.transport = TransportType(args.transport)
    settings.mcp.host = args.host
    settings.mcp.port = args.port
    settings.mcp.server_name = args.name
    settings.mcp.version = args.version

    # 更新日志配置
    from src.core.config.config import LogLevel, LogOutput
    settings.logging.level = LogLevel(args.log_level)
    settings.logging.file_path = args.log_file

    # 更新功能开关
    if args.no_tools:
        settings.features.tools = False
    if args.no_resources:
        settings.features.resources = False
    if args.no_prompts:
        settings.features.prompts = False

    # 设置配置文件路径
    settings.config_file = args.config


def print_startup_info(server, args):
    """打印启动信息"""
    from src.core.logging.logger import get_logger

    logger = get_logger("main")

    logger.info("=" * 60)
    logger.info(f"QiuChi Server v{settings.mcp.version}")
    logger.info("=" * 60)
    logger.info(f"Server: {settings.mcp.server_name}")
    logger.info(f"Transport: {settings.mcp.transport.value}")

    if settings.mcp.transport.value in ["sse", "streamable-http"]:
        logger.info(f"Listening: http://{settings.mcp.host}:{settings.mcp.port}")

    logger.info(f"Features: Tools={settings.features.tools}, "
                f"Resources={settings.features.resources}, "
                f"Prompts={settings.features.prompts}")
    logger.info(f"Log level: {settings.logging.level.value}")
    logger.info(f"Config file: {settings.config_file}")
    logger.info("=" * 60)


def main_async():
    """主函数"""
    # 解析参数
    args = parse_arguments()

    # 更新配置
    update_settings_from_args(args)

    # 设置日志
    setup_logging(
        level=settings.logging.level.value,
        output=settings.logging.output.value,
        file_path=settings.logging.file_path,
    )

    # 创建服务器（插件将通过自动发现机制加载）
    server = create_server(
        name=settings.mcp.server_name,
        version=settings.mcp.version,
    )

    # 打印启动信息
    print_startup_info(server, args)

    # 启动服务器
    server.run(
        transport=settings.mcp.transport.value,
        host=settings.mcp.host,
        port=settings.mcp.port,
    )


def main():
    """主函数"""
    try:
        main_async()
    except KeyboardInterrupt:
        from src.core.logging.logger import get_logger
        logger = get_logger("main")
        logger.info("Server stopped by user")
        sys.exit(0)
    except Exception as e:
        from src.core.logging.logger import get_logger
        logger = get_logger("main")
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()