"""
请求 ID 基础设施（request_id）

为每个 HTTP 请求确定贯穿全链路的 ``request_id``，用于日志串联与问题排查。
本项目不依赖 OpenTelemetry 等第三方可观测性体系，request_id 是纯日志链路追踪的最小形态：

    - ``request_id_var`` — 请求级 ContextVar（异步安全），默认 ``"-"``
    - ``get_request_id`` — 供业务代码（wrapper / 协议中间件）读取当前请求 id
    - ``RequestIDMiddleware`` — HTTP 传输层中间件（最外层）：
      优先复用上游 ``X-Request-ID`` 请求头（网关链路追踪），否则生成 UUID；
      写入 request.state 与 ContextVar，通过 loguru ``contextualize`` 贯穿日志，
      并在响应头回写。

挂载（FastMCP app 外层，Starlette 栈式）::

    app.add_middleware(RequestIDMiddleware)

Usage:
    from src.infras.request_id import RequestIDMiddleware, get_request_id
    rid = get_request_id()  # 未处于请求上下文时返回 "-"
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar

from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# 请求级 request_id（contextvar，异步安全）
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

__all__ = [
    "request_id_var",
    "get_request_id",
    "RequestIDMiddleware",
]


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
        with logger.contextualize(request_id=rid):
            response: Response = await call_next(request)
            response.headers[self.header_name] = rid
            return response
