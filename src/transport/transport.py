"""
传输层实现

传输配置解析、请求 ID 注入与 MCP 服务承载：
- 传输类型解析（stdio / SSE / streamable-http）
- 传输配置构造（TransportConfig / get_transport_config）
- 请求 ID 注入（request_id_var / get_request_id / RequestIDMiddleware）
- 服务承载（serve_mcp：stdio 直连或 uvicorn 运行 HTTP app）

请求 ID 是纯日志链路追踪的最小形态（不依赖 OpenTelemetry 等第三方可观测性体系）：
HTTP 传输层最外层中间件为每个请求确定 request_id（优先复用上游 X-Request-ID，
否则生成 UUID），写入 ContextVar 供插件 wrapper 与协议中间件读取，并贯穿日志。
"""

import uuid
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from loguru import logger as loguru_logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# 从共享类型模块导入
from src.constants.enums import TransportType
from src.core.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# 请求 ID：请求级 ContextVar（异步安全），默认 "-"
# ---------------------------------------------------------------------------

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


def get_request_id() -> str:
    """获取当前请求的 request_id（未在请求上下文时返回 "-"）。"""
    return request_id_var.get()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """请求 ID 注入中间件（HTTP 传输层，最外层）。

    职责单一：为每个 HTTP 请求确定贯穿全链路的 ``request_id``。
    优先复用上游传入的 ``X-Request-ID`` 请求头（网关链路追踪场景），否则生成 UUID；
    将 request_id 写入 ``request.state.request_id`` 与全局 ``request_id_var``（ContextVar），
    并通过 loguru ``contextualize`` 让该请求作用域内的所有日志自动携带 request_id；
    最后在响应头回写，供客户端 / 网关继续追踪。

    必须挂在 FastMCP app 外层且**最早**执行，以保证下游
    （wrapper 的 ``get_request_id()``、协议中间件、日志）都能取到真实 request_id。

    Attributes:
        app: ASGI 应用实例
        header_name: request_id 请求 / 响应头名称，默认 ``X-Request-ID``
    """

    def __init__(self, app, header_name: str = "X-Request-ID") -> None:
        super().__init__(app)
        self.header_name: str = header_name

    async def dispatch(self, request: Request, call_next) -> Response:
        rid = request.headers.get(self.header_name) or str(uuid.uuid4())
        request.state.request_id = rid
        request_id_var.set(rid)
        # contextualize 基于 contextvars，自动传播到所有 async 子任务
        with loguru_logger.contextualize(request_id=rid):
            response: Response = await call_next(request)
            response.headers[self.header_name] = rid
            return response


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
    # request_id 注入：挂 HTTP 传输层最外层中间件，保证下游（wrapper / 协议中间件 / 日志）可取到真实 id
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
