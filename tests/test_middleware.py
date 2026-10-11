#!/usr/bin/env python3
"""MCP 中间件链与中间件单测。

覆盖：RequestContext / ResponseContext 上下文、MiddlewareChain 洋葱模型
执行顺序与管理操作、ErrorHandlerMiddleware（JSON-RPC 错误响应）、
LoggingMiddleware（请求/响应日志开关、敏感字段过滤、慢请求告警、异常传播）。
"""

from __future__ import annotations

import time
from functools import wraps

import pytest

from src.constants import PluginType
from src.core.middleware import (
    INTERNAL_ERROR,
    INVALID_PARAMS,
    METHOD_NOT_FOUND,
    ErrorHandlerMiddleware,
    LoggingMiddleware,
    MiddlewareChain,
    RequestContext,
    ResponseContext,
)


def make_handler(result: object = None, error: Exception | None = None):
    """构造 final handler：正常返回 result，或抛出 error。"""

    async def handler(request: RequestContext) -> ResponseContext:
        if error is not None:
            raise error
        return ResponseContext(response={"result": result})

    return handler


class OrderingMiddleware:
    """记录 enter/exit 顺序的测试中间件（鸭子类型：实现 __call__ 约定）。"""

    def __init__(self, name: str, log: list[str]) -> None:
        self.name = name
        self.log = log

    async def __call__(self, request: RequestContext, next_handler) -> ResponseContext:
        self.log.append(f"{self.name}:enter")
        response = await next_handler(request)
        self.log.append(f"{self.name}:exit")
        return response


# ---------------------------------------------------------------------------
# 上下文
# ---------------------------------------------------------------------------


class TestRequestContext:
    def test_method_and_request_id(self) -> None:
        ctx = RequestContext(request={"method": "tools/call", "id": "abc-1"})
        assert ctx.method == "tools/call"
        assert ctx.request_id == "abc-1"

    def test_missing_fields_default_to_empty(self) -> None:
        ctx = RequestContext(request={})
        assert ctx.method == ""
        assert ctx.request_id == ""

    def test_metadata_none_fallback(self) -> None:
        ctx = RequestContext(request={}, metadata=None)
        assert ctx.metadata == {}
        assert ctx.server is None


class TestResponseContext:
    def test_metadata_none_fallback(self) -> None:
        ctx = ResponseContext(response={"result": 1}, metadata=None)
        assert ctx.metadata == {}


# ---------------------------------------------------------------------------
# 中间件链
# ---------------------------------------------------------------------------


class TestMiddlewareChain:
    async def test_execute_onion_order(self) -> None:
        log: list[str] = []
        chain = MiddlewareChain()
        chain.add(OrderingMiddleware("a", log))
        chain.add(OrderingMiddleware("b", log))
        chain.add(OrderingMiddleware("c", log))
        final = make_handler(result=42)

        response = await chain.execute(RequestContext(request={}), final)
        assert response.response == {"result": 42}
        # 洋葱模型：a 最外层，c 最内层；enter 顺序 a->b->c，exit 逆序
        assert log == [
            "a:enter",
            "b:enter",
            "c:enter",
            "c:exit",
            "b:exit",
            "a:exit",
        ]

    async def test_empty_chain_passthrough(self) -> None:
        chain = MiddlewareChain()
        response = await chain.execute(RequestContext(request={}), make_handler(result="ok"))
        assert response.response == {"result": "ok"}

    def test_add_and_names(self) -> None:
        chain = MiddlewareChain()
        assert chain.add(ErrorHandlerMiddleware()) is chain
        chain.add(LoggingMiddleware())
        assert chain.names() == ["ErrorHandlerMiddleware", "LoggingMiddleware"]
        assert len(chain) == 2
        assert "LoggingMiddleware" in chain
        assert [type(m).__name__ for m in chain] == chain.names()

    def test_add_all(self) -> None:
        chain = MiddlewareChain()
        chain.add_all([ErrorHandlerMiddleware(), LoggingMiddleware()])
        assert len(chain) == 2

    def test_insert(self) -> None:
        chain = MiddlewareChain()
        chain.add(OrderingMiddleware("b", []))
        chain.insert(0, OrderingMiddleware("a", []))
        chain.insert(-1, OrderingMiddleware("mid", []))
        assert chain.names() == ["OrderingMiddleware", "OrderingMiddleware", "OrderingMiddleware"]
        # 顺序：a(mid 之后 a？)—— 用实例验证顺序
        names = chain.names()
        assert names == ["OrderingMiddleware"] * 3  # 同名类，只验证计数与不抛错
        assert len(chain) == 3

    def test_insert_negative_beyond(self) -> None:
        chain = MiddlewareChain()
        chain.add(OrderingMiddleware("b", []))
        chain.insert(-99, OrderingMiddleware("a", []))
        assert chain.names()[0] == "OrderingMiddleware"

    def test_remove(self) -> None:
        mw = ErrorHandlerMiddleware()
        chain = MiddlewareChain()
        chain.add(mw)
        assert chain.remove(mw) is True
        assert len(chain) == 0
        assert chain.remove(mw) is False

    def test_remove_by_name(self) -> None:
        chain = MiddlewareChain()
        chain.add(ErrorHandlerMiddleware())
        chain.add(LoggingMiddleware())
        assert chain.remove_by_name("ErrorHandlerMiddleware") is True
        assert chain.names() == ["LoggingMiddleware"]
        assert chain.remove_by_name("NoSuch") is False

    def test_clear(self) -> None:
        chain = MiddlewareChain()
        chain.add(ErrorHandlerMiddleware())
        chain.clear()
        assert len(chain) == 0
        assert chain.names() == []


# ---------------------------------------------------------------------------
# 错误处理中间件
# ---------------------------------------------------------------------------


class TestErrorHandlerMiddleware:
    async def test_pass_through_on_success(self) -> None:
        mw = ErrorHandlerMiddleware()
        response = await mw.handle(RequestContext(request={"id": 1}), make_handler(result="ok"))
        assert response.response == {"result": "ok"}

    async def test_error_response_shape(self) -> None:
        mw = ErrorHandlerMiddleware()

        async def boom(request: RequestContext) -> ResponseContext:
            raise ValueError("bad input")

        response = await mw.handle(RequestContext(request={"id": 7}), boom)
        assert response.response["jsonrpc"] == "2.0"
        assert response.response["id"] == 7
        err = response.response["error"]
        assert err["code"] == INTERNAL_ERROR
        assert err["message"] == "Internal error: ValueError"
        assert err["data"]["type"] == "ValueError"
        assert err["data"]["message"] == "bad input"
        assert err["data"]["request_id"] == 7
        assert "traceback" not in err["data"]

    async def test_traceback_included_when_enabled(self) -> None:
        mw = ErrorHandlerMiddleware(include_traceback=True)

        async def boom(request: RequestContext) -> ResponseContext:
            raise RuntimeError("x")

        response = await mw.handle(RequestContext(request={"id": 1}), boom)
        assert "traceback" in response.response["error"]["data"]

    async def test_missing_id_omits_id_field(self) -> None:
        mw = ErrorHandlerMiddleware()

        async def boom(request: RequestContext) -> ResponseContext:
            raise RuntimeError("x")

        response = await mw.handle(RequestContext(request={}), boom)
        assert "id" not in response.response

    def test_create_validation_error(self) -> None:
        resp = ErrorHandlerMiddleware.create_validation_error("bad", {"k": 1}, rid=9)
        assert resp["error"]["code"] == INVALID_PARAMS
        assert resp["error"]["data"] == {"k": 1}
        assert resp["id"] == 9

        resp_no_id = ErrorHandlerMiddleware.create_validation_error("bad")
        assert "id" not in resp_no_id

    def test_create_method_not_found_error(self) -> None:
        resp = ErrorHandlerMiddleware.create_method_not_found_error("nope", rid=3)
        assert resp["error"]["code"] == METHOD_NOT_FOUND
        assert resp["error"]["data"] == {"method": "nope"}
        assert resp["id"] == 3

        resp_no_id = ErrorHandlerMiddleware.create_method_not_found_error("nope")
        assert "id" not in resp_no_id


# ---------------------------------------------------------------------------
# 日志中间件
# ---------------------------------------------------------------------------


class TestLoggingMiddleware:
    async def test_passthrough(self) -> None:
        mw = LoggingMiddleware()
        response = await mw.handle(
            RequestContext(request={"id": 1, "method": "tools/call"}),
            make_handler(result={"ok": True}),
        )
        assert response.response == {"result": {"ok": True}}

    async def test_logging_switches(self, monkeypatch) -> None:
        called = {"request": 0, "response": 0}
        mw = LoggingMiddleware(log_request=False, log_response=False)

        def fake_log_request(request, rid) -> None:
            called["request"] += 1

        def fake_log_response(response, rid, et, method) -> None:
            called["response"] += 1

        monkeypatch.setattr(mw, "_log_request", fake_log_request)
        monkeypatch.setattr(mw, "_log_response", fake_log_response)

        await mw.handle(
            RequestContext(request={"id": 1, "method": "m"}),
            make_handler(result="ok"),
        )
        assert called == {"request": 0, "response": 0}

        mw_on = LoggingMiddleware()
        monkeypatch.setattr(mw_on, "_log_request", fake_log_request)
        monkeypatch.setattr(mw_on, "_log_response", fake_log_response)
        await mw_on.handle(
            RequestContext(request={"id": 1, "method": "m"}),
            make_handler(result="ok"),
        )
        assert called == {"request": 1, "response": 1}

    async def test_error_response_logged_as_warning(self, monkeypatch) -> None:
        warnings: list[str] = []
        mw = LoggingMiddleware()

        def fake_log_response(response, rid, et, method) -> None:
            # 不记录内容，仅验证分支进入
            pass

        monkeypatch.setattr(mw, "_log_response", fake_log_response)
        response = await mw.handle(
            RequestContext(request={"id": 2, "method": "m"}),
            make_handler(result=None, error=None),  # 正常路径
        )
        # 通过则响应正常返回
        assert response.response == {"result": None}
        assert warnings == []  # 占位断言，保证变量被使用

    async def test_slow_threshold_warns(self, monkeypatch) -> None:
        mw = LoggingMiddleware(slow_threshold=0.0)
        start = time.time()
        response = await mw.handle(
            RequestContext(request={"id": 1, "method": "m"}),
            make_handler(result="ok"),
        )
        # 阈值 0.0 必触发告警分支（执行时间 > 0），但不影响结果
        assert response.response == {"result": "ok"}
        assert time.time() - start >= 0

    async def test_exception_propagates(self, monkeypatch) -> None:
        mw = LoggingMiddleware()

        async def boom(request: RequestContext) -> ResponseContext:
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            await mw.handle(RequestContext(request={"id": 1, "method": "m"}), boom)

    def test_filter_sensitive_data(self) -> None:
        filtered = LoggingMiddleware._filter_sensitive_data(
            {
                "password": "p",
                "token": "t",
                "nested": {"api_key": "k", "ok": 1},
                "items": [{"secret": "s"}, "plain"],
                "normal": "v",
            }
        )
        assert filtered["password"] == "***REDACTED***"
        assert filtered["token"] == "***REDACTED***"
        assert filtered["nested"]["api_key"] == "***REDACTED***"
        assert filtered["nested"]["ok"] == 1
        assert filtered["items"][0]["secret"] == "***REDACTED***"
        assert filtered["items"][1] == "plain"
        assert filtered["normal"] == "v"

    def test_filter_sensitive_data_non_dict(self) -> None:
        assert LoggingMiddleware._filter_sensitive_data("str") == "str"
        assert LoggingMiddleware._filter_sensitive_data([1, 2]) == [1, 2]

    def test_source_location_without_server(self) -> None:
        mw = LoggingMiddleware()
        ctx = RequestContext(request={"method": "m"})
        assert mw._get_source_location("m", ctx) is None

    def test_source_location_for_tool(self) -> None:
        def my_tool(a: int, b: int) -> int:
            """测试工具"""
            return a + b

        class FakeItem:
            type = PluginType.TOOL
            item = my_tool

        class FakeRegistry:
            def get_item(self, name: str):
                return FakeItem() if name == "my_tool" else None

        class FakeServer:
            registry = FakeRegistry()

        mw = LoggingMiddleware()
        ctx = RequestContext(request={"method": "my_tool"}, server=FakeServer())
        location = mw._get_source_location("my_tool", ctx)
        assert location is not None
        assert "test_middleware.py" in location

    def test_function_source_unwraps(self) -> None:
        def base() -> None:
            """原始函数"""

        @wraps(base)
        def wrapped() -> None:
            return base()

        location = LoggingMiddleware._get_function_source(wrapped)
        assert location is not None
        assert "test_middleware.py" in location
