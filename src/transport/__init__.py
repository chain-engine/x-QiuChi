"""
传输层模块

提供多种传输方式支持：
- stdio: 标准输入/输出（Claude Desktop 兼容）
- sse: Server-Sent Events
- streamable-http: 可流式 HTTP（FastMCP 默认）
"""

from .transport import (
    TransportConfig,
    TransportType,
    get_transport_config,
    serve_mcp,
)

__all__ = [
    "TransportType",
    "TransportConfig",
    "get_transport_config",
    "serve_mcp",
]
