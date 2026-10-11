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

    描述一次服务承载所需的传输类型与监听地址。
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

    def validate(self) -> bool:
        """
        验证配置

        Returns:
            配置是否有效
        """
        # 检查端口范围
        return 1 <= self.port <= 65535


# 预定义的传输配置
TRANSPORT_PRESETS: dict[str, TransportConfig] = {
    "stdio": TransportConfig(transport=TransportType.STDIO),
    "sse": TransportConfig(transport=TransportType.SSE),
    "http": TransportConfig(transport=TransportType.STREAMABLE_HTTP),
}


def get_transport_config(
    transport: str | TransportType,
    host: str = "0.0.0.0",
    port: int = 8888,
    preset: str | None = None,
) -> TransportConfig:
    """
    获取传输配置的便捷函数

    Args:
        transport: 传输类型字符串或枚举
        host: HTTP 模式监听地址
        port: HTTP 模式监听端口
        preset: 预设配置名称

    Returns:
        TransportConfig: 传输配置实例

    Example:
        >>> config = get_transport_config("stdio")
        >>> config.transport
        <TransportType.STDIO: 'stdio'>
    """
    # 使用预设配置
    if preset and preset in TRANSPORT_PRESETS:
        config = TRANSPORT_PRESETS[preset]
        config.host = host
        config.port = port
        return config

    # 从字符串创建
    if isinstance(transport, str):
        return TransportConfig.from_string(transport, host, port)

    # 直接使用枚举
    return TransportConfig(transport=transport, host=host, port=port)


async def serve_mcp(mcp: Any, config: TransportConfig) -> None:
    """以指定传输方式承载 FastMCP 实例。

    stdio 直接走 SDK 的 run_stdio_async；SSE / streamable-http 构建 ASGI app
    后以 uvicorn 运行，外层挂载 QiuChiHTTPMiddleware（真实 request_id 注入 +
    OpenTelemetry 埋点）。认证由 FastMCP 官方 RequireAuthMiddleware 在 app 内部处理。

    Args:
        mcp: FastMCP 实例
        config: 传输配置
    """
    logger.info(f"Starting MCP transport: {config.transport.value}")
    if config.transport == TransportType.STDIO:
        await mcp.run_stdio_async()
    elif config.transport == TransportType.SSE:
        logger.info(f"Listening on {config.host}:{config.port}")
        await _serve_http_app(mcp.sse_app(), config)
    elif config.transport == TransportType.STREAMABLE_HTTP:
        logger.info(f"Listening on {config.host}:{config.port}")
        await _serve_http_app(mcp.streamable_http_app(), config)
    else:
        raise ValueError(f"Unsupported transport type: {config.transport.value}")


async def _serve_http_app(app: Any, config: TransportConfig) -> None:
    """以 uvicorn 运行 MCP HTTP ASGI app。"""
    from src.core.opentelemetry import QiuChiHTTPMiddleware, setup_telemetry

    setup_telemetry()
    app.add_middleware(QiuChiHTTPMiddleware)

    import uvicorn

    uvicorn_config = uvicorn.Config(
        app,
        host=config.host,
        port=config.port,
        log_level="info",
    )
    server = uvicorn.Server(uvicorn_config)
    await server.serve()
