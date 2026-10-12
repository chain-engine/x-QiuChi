"""
传输层实现

传输配置解析与 MCP 服务承载：
- 传输类型解析（stdio / SSE / streamable-http）
- 传输配置构造（TransportConfig / get_transport_config）
- 服务承载（serve_mcp：stdio 直连或 uvicorn 运行 HTTP app）
"""

from dataclasses import dataclass
from typing import Any

# 从共享类型模块导入
from src.constants.enums import TransportType
from src.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TransportConfig:
    """
    传输层配置

    描述一次服务承载所需的传输类型与监听地址，默认 streamable-http。
    """

    transport: TransportType = TransportType.STREAMABLE_HTTP
    host: str = "0.0.0.0"
    port: int = 8888

    @classmethod
    def from_string(
        cls,
        transport_str: str,
        host: str = "0.0.0.0",
        port: int = 8888,
    ) -> "TransportConfig":
        """
        从字符串创建传输配置

        Args:
            transport_str: 传输类型字符串 (stdio, sse, streamable-http)
            host: HTTP 模式监听地址
            port: HTTP 模式监听端口

        Returns:
            TransportConfig: 传输配置实例

        Raises:
            ValueError: 无效的传输类型
        """
        transport_map = {
            "stdio": TransportType.STDIO,
            "sse": TransportType.SSE,
            "streamable-http": TransportType.STREAMABLE_HTTP,
        }

        if transport_str not in transport_map:
            raise ValueError(
                f"Invalid transport type: {transport_str}. "
                f"Valid options: {list(transport_map.keys())}"
            )

        return cls(
            transport=transport_map[transport_str],
            host=host,
            port=port,
        )


def get_transport_config(
    transport: str | TransportType,
    host: str = "0.0.0.0",
    port: int = 8888,
) -> TransportConfig:
    """
    获取传输配置的便捷函数

    Args:
        transport: 传输类型字符串或枚举
        host: HTTP 模式监听地址
        port: HTTP 模式监听端口

    Returns:
        TransportConfig: 传输配置实例

    Example:
        >>> config = get_transport_config("stdio")
        >>> config.transport
        <TransportType.STDIO: 'stdio'>
    """
    # 从字符串创建
    if isinstance(transport, str):
        return TransportConfig.from_string(transport, host, port)

    # 直接使用枚举
    return TransportConfig(transport=transport, host=host, port=port)


async def _serve_http_app(app: Any, config: TransportConfig) -> None:
    """以 uvicorn 运行 MCP HTTP ASGI app。"""
    # request_id 注入：挂 HTTP 传输层最外层中间件（纯日志链路追踪，无第三方可观测性依赖）
    from src.infras.request_id import RequestIDMiddleware

    app.add_middleware(RequestIDMiddleware)

    # uvicorn 负责 HTTP 协议解析与连接管理；认证由 app 内部的 RequireAuthMiddleware 处理
    import uvicorn

    uvicorn_config = uvicorn.Config(
        app,
        host=config.host,
        port=config.port,
        log_level="info",
    )
    server = uvicorn.Server(uvicorn_config)
    # 阻塞处理请求，直到收到停止信号（Ctrl+C / SIGTERM）
    await server.serve()


async def serve_mcp(mcp: Any, config: TransportConfig) -> None:
    """以指定传输方式承载 FastMCP 实例，阻塞直到服务停止。

    Args:
        mcp: FastMCP 实例
        config: 传输配置
    """
    logger.info(f"Starting MCP transport: {config.transport.value}")
    if config.transport == TransportType.STDIO:
        # 标准输入输出直连：客户端以子进程方式拉起本服务，通过进程 stdin/stdout 通信
        await mcp.run_stdio_async()
    elif config.transport == TransportType.SSE:
        logger.info(f"Listening on {config.host}:{config.port}")
        # SSE：构建 ASGI app，GET 建立长连接接收服务端推送，POST 发送请求
        await _serve_http_app(mcp.sse_app(), config)
    elif config.transport == TransportType.STREAMABLE_HTTP:
        logger.info(f"Listening on {config.host}:{config.port}")
        # Streamable-HTTP（默认传输方式）：单一 HTTP 端点，POST 请求-响应，可选升级为 SSE 流式下行
        await _serve_http_app(mcp.streamable_http_app(), config)
    else:
        raise ValueError(f"Unsupported transport type: {config.transport.value}")
