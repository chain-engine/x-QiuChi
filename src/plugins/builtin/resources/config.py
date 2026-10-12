"""
配置资源示例

展示如何使用 QiuChi 的资源装饰器创建资源。
"""

from src.plugins import resource


@resource(name="config://server", category="system", tags=["configuration"])
def get_server_config() -> str:
    """
    获取服务器配置

    Returns:
        服务器配置的 JSON 字符串
    """
    import json

    config = {
        "name": "QiuChi Server",
        "version": "1.0.0",
        "transport": "streamable-http",
        "port": 8888,
        "features": {
            "tools": True,
            "resources": True,
            "prompts": True,
        },
    }
    return json.dumps(config, indent=2, ensure_ascii=False)


@resource(name="config://version", category="system", tags=["info"])
def get_version_info() -> str:
    """
    获取版本信息

    Returns:
        版本信息的 JSON 字符串
    """
    import json

    info = {
        "name": "QiuChi",
        "version": "1.0.0",
        "description": "一个生产级 MCP（Model Context Protocol）服务器框架",
        "author": "John Young <john.young@foxmail.com>",
        "license": "MIT",
    }
    return json.dumps(info, indent=2, ensure_ascii=False)


@resource(name="docs://api", category="documentation", tags=["docs", "api"])
def get_api_documentation() -> str:
    """
    获取 API 文档

    Returns:
        API 文档的 Markdown 格式
    """
    return """
# 秋池 MCP 服务器 API 文档

## 概述
秋池（QiuChi）是一个生产级 MCP（Model Context Protocol）服务器框架。

## 可用工具
- `add`：两数相加
- `subtract`：两数相减
- `multiply`：两数相乘
- `divide`：两数相除
- `sqrt`：开平方

## 可用资源
- `config://server`：服务器配置
- `config://version`：版本信息
- `docs://api`：本文档

## 使用方式
使用任意 MCP 兼容客户端连接服务器即可。
"""


__all__ = [
    "get_server_config",
    "get_version_info",
    "get_api_documentation",
]
