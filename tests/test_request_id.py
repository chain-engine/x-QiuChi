"""传输层请求 ID 单测：ContextVar 默认值、RequestIDMiddleware HTTP 行为。"""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.testclient import TestClient

from src.transport.transport import (
    RequestIDMiddleware,
    get_request_id,
)


def test_get_request_id_default() -> None:
    """未处于请求上下文时，request_id 返回 "-"。"""
    assert get_request_id() == "-"


def _build_request_id_app(header_name: str = "X-Request-ID") -> Starlette:
    """构建挂载 RequestIDMiddleware 的最小 ASGI app（返回 request_id 供断言）。"""
    app = Starlette()

    @app.route("/")
    async def root(request):
        return JSONResponse({"state": request.state.request_id, "ctx": get_request_id()})

    app.add_middleware(RequestIDMiddleware, header_name=header_name)
    return app


def test_request_id_middleware_reuses_header() -> None:
    """携带 X-Request-ID 时复用：state / ContextVar / 响应头三者一致。"""
    with TestClient(_build_request_id_app()) as client:
        resp = client.get("/", headers={"X-Request-ID": "rid-abc-123"})
    assert resp.json() == {"state": "rid-abc-123", "ctx": "rid-abc-123"}
    assert resp.headers["X-Request-ID"] == "rid-abc-123"


def test_request_id_middleware_generates_uuid() -> None:
    """未携带头时生成 UUID：非默认值、回写响应头。"""
    with TestClient(_build_request_id_app()) as client:
        resp = client.get("/")
    rid = resp.json()["state"]
    assert rid and rid != "-"
    assert resp.headers["X-Request-ID"] == rid


def test_request_id_middleware_custom_header() -> None:
    """自定义请求头名称生效。"""
    with TestClient(_build_request_id_app(header_name="X-Trace-ID")) as client:
        resp = client.get("/", headers={"X-Trace-ID": "trace-1"})
    assert resp.json() == {"state": "trace-1", "ctx": "trace-1"}
    assert resp.headers["X-Trace-ID"] == "trace-1"
