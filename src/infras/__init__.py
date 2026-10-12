"""
基础设施层（infrastructure）

承载与第三方基础设施集成的能力，与业务编排（core / server）解耦：
- request_id：请求 ID 基础设施（ContextVar + RequestIDMiddleware，纯日志链路追踪）
"""

from src.infras.request_id import (
    RequestIDMiddleware,
    get_request_id,
    request_id_var,
)

__all__ = [
    "request_id_var",
    "get_request_id",
    "RequestIDMiddleware",
]
