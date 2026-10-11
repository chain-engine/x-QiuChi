"""
基础设施层（infrastructure）

承载与第三方基础设施 / 可观测性集成的能力，与业务编排（core / server）解耦：
- opentelemetry：OpenTelemetry 可观测性接入（tracing / metrics / request_id）
"""

from src.infras.opentelemetry import (
    QiuChiHTTPMiddleware,
    get_meter,
    get_request_id,
    get_tracer,
    setup_telemetry,
)

__all__ = [
    "setup_telemetry",
    "QiuChiHTTPMiddleware",
    "get_tracer",
    "get_meter",
    "get_request_id",
]
