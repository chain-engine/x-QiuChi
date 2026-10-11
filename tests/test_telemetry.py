"""可观测性模块单测：setup_telemetry 幂等与 request_id contextvar。"""

from __future__ import annotations

from src.core.opentelemetry import (
    get_request_id,
    get_tracer,
    setup_telemetry,
)


def test_get_request_id_default() -> None:
    """未处于请求上下文时，request_id 返回 "-"。"""
    assert get_request_id() == "-"


def test_setup_telemetry_idempotent() -> None:
    """setup_telemetry 多次调用不抛错、不重复初始化。"""
    setup_telemetry()
    setup_telemetry()  # 第二次调用应直接返回


def test_setup_telemetry_initializes_tracer() -> None:
    """默认配置（console exporter）下应初始化 tracer。"""
    setup_telemetry()
    tracer = get_tracer()
    assert tracer is not None
