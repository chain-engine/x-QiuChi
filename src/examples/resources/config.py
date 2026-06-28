"""
配置资源示例

展示如何使用 QiuChi 的资源装饰器创建资源。
"""

from src import resource


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
        "port": 8000,
        "features": {
            "tools": True,
            "resources": True,
            "prompts": True,
        }
    }
    return json.dumps(config, indent=2)


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
        "description": "Enterprise-grade MCP Server Framework",
        "author": "John Young <john.young@foxmail.com>",
        "license": "MIT",
    }
    return json.dumps(info, indent=2)


@resource(name="docs://api", category="documentation", tags=["docs", "api"])
def get_api_documentation() -> str:
    """
    获取 API 文档

    Returns:
        API 文档的 Markdown 格式
    """
    return """
# QiuChi MCP Server API Documentation

## Overview
QiuChi is an enterprise-grade MCP (Model Context Protocol) server framework.

## Available Tools
- `add`: Add two numbers
- `subtract`: Subtract two numbers
- `multiply`: Multiply two numbers
- `divide`: Divide two numbers

## Available Resources
- `config://server`: Server configuration
- `config://version`: Version information
- `docs://api`: This documentation

## Usage
Connect to the server using any MCP-compatible client.
"""


__all__ = [
    "get_server_config",
    "get_version_info",
    "get_api_documentation",
]