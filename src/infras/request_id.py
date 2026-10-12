"""
OpenTelemetry 可观测性接入

提供:
    - ``setup_telemetry`` — 初始化 TracerProvider / MeterProvider（console 或 OTLP）
    - ``QiuChiHTTPMiddleware`` — 挂在 MCP HTTP 传输层外层的 Starlette 中间件：
      注入真实 ``request_id``（X-Request-ID 或自动生成，贯穿日志）、
      记录 HTTP 请求 span 与计数器/直方图
    - ``get_tracer`` / ``get_meter`` / ``get_request_id`` — 供业务代码取用

配置（config.yaml / 环境变量 TELEMETRY_*）::

    opentelemetry:
      enabled: true
      service_name: "x-QiuChi"
      exporter: "console"        # console | otlp
      otlp_endpoint: ""          # exporter=otlp 时填写，如 http://localhost:4318/v1/traces

说明: console 模式只输出 tracing span（便于开发观察）；
otlp 模式启用 metrics + tracing 全量导出（接 Jaeger / OTel Collector 等）。
"""

from __future__ import annotations

import time
import uuid
from contextvars import ContextVar

from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.core.config import settings

_configured: bool = False
_tracer = None
_meter = None

# 请求级 request_id（contextvar，异步安全）
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

__all__ = [
    "setup_telemetry",
    "QiuChiHTTPMiddleware",
    "get_tracer",
    "get_meter",
    "get_request_id",
]


def get_request_id() -> str:
    """获取当前请求的 request_id（未在请求上下文时返回 "-"）。"""
    return request_id_var.get()


def setup_telemetry() -> None:
    """初始化 OpenTelemetry（幂等）。"""
    global _configured, _tracer, _meter

    if _configured:
        return
    _configured = True

    if not settings.telemetry.enabled:
        logger.debug("Telemetry disabled by config")
        return

    from opentelemetry import metrics, trace
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import (
        ConsoleSpanExporter,
        SimpleSpanProcessor,
        SpanExporter,
    )

    resource = Resource.create({SERVICE_NAME: settings.telemetry.service_name})
    use_otlp = settings.telemetry.exporter == "otlp" and settings.telemetry.otlp_endpoint

    span_exporter: SpanExporter
    if use_otlp:
        span_exporter = OTLPSpanExporter(endpoint=settings.telemetry.otlp_endpoint)
    else:
        span_exporter = ConsoleSpanExporter()

    trace_provider = TracerProvider(resource=resource)
    trace_provider.add_span_processor(SimpleSpanProcessor(span_exporter))
    trace.set_tracer_provider(trace_provider)
    _tracer = trace.get_tracer(settings.telemetry.service_name)

    if use_otlp:
        metric_reader = PeriodicExportingMetricReader(
            OTLPMetricExporter(endpoint=settings.telemetry.otlp_endpoint),
            export_interval_millis=30_000,
        )
        meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
        metrics.set_meter_provider(meter_provider)
        _meter = metrics.get_meter(settings.telemetry.service_name)
    else:
        # console 模式不启用 metrics，避免周期性刷屏；OTLP 模式全量导出
        _meter = None

    logger.info(
        f"Telemetry initialized (service={settings.telemetry.service_name}, "
        f"exporter={settings.telemetry.exporter})"
    )


def get_tracer():
    """获取全局 Tracer（惰性初始化）。"""
    if not _configured:
        setup_telemetry()
    return _tracer


def get_meter():
    """获取全局 Meter（惰性初始化，console 模式下为 None）。"""
    if not _configured:
        setup_telemetry()
    return _meter


class QiuChiHTTPMiddleware(BaseHTTPMiddleware):
    """MCP HTTP 传输层中间件。

    负责:
    1. 注入真实 request_id：优先取 ``X-Request-ID`` 请求头，否则生成 uuid；
       通过 loguru ``contextualize`` 贯穿整个请求的日志输出。
    2. OpenTelemetry 埋点：HTTP 请求 span、请求计数、耗时直方图。

    挂在 ``FastMCP.streamable_http_app()`` / ``FastMCP.sse_app()`` 外层。
    """

    def __init__(self, app) -> None:
        super().__init__(app)
        self._tracer = get_tracer()
        self._meter = get_meter()
        self._requests_total = None
        self._request_duration = None
        if self._meter is not None:
            self._requests_total = self._meter.create_counter(
                "mcp.http.requests_total",
                unit="1",
                description="Total MCP HTTP requests",
            )
            self._request_duration = self._meter.create_histogram(
                "mcp.http.request.duration",
                unit="s",
                description="MCP HTTP request duration",
            )

    async def dispatch(self, request: Request, call_next) -> Response:
        rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request_id_var.set(rid)
        start = time.perf_counter()
        status_code = 500

        with logger.contextualize(request_id=rid):
            try:
                if self._tracer is not None:
                    with self._tracer.start_as_current_span(
                        "mcp.http.request",
                        attributes={
                            "http.request.method": request.method,
                            "url.path": request.url.path,
                            "request_id": rid,
                        },
                    ) as span:
                        response: Response = await call_next(request)
                        status_code = response.status_code
                        span.set_attribute("http.response.status_code", status_code)
                        return response

                resp: Response = await call_next(request)
                status_code = resp.status_code
                return resp
            finally:
                if self._requests_total is not None:
                    self._requests_total.add(
                        1,
                        {"http.method": request.method, "http.status": str(status_code)},
                    )
                if self._request_duration is not None:
                    self._request_duration.record(
                        time.perf_counter() - start,
                        {"http.method": request.method},
                    )
