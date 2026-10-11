"""运行时上下文单测：RequestContext 与 ContextManager。"""

from __future__ import annotations

from src.runtime.context import (
    ContextManager,
    RequestContext,
    clear_current_context,
    get_current_context,
)


def test_request_context_defaults() -> None:
    ctx = RequestContext()
    assert ctx.request_id
    assert ctx.metadata == {}
    assert ctx.server is None
    assert ctx.session_id is None


def test_request_context_metadata() -> None:
    ctx = RequestContext()
    ctx.update_metadata("key", "value")
    assert ctx.get_metadata("key") == "value"
    assert ctx.get_metadata("missing", "fallback") == "fallback"
    assert ctx.get_metadata("missing") is None


def test_request_context_to_dict() -> None:
    ctx = RequestContext(
        request_id="rid-1",
        session_id="s1",
        user={"name": "tester"},
    )
    d = ctx.to_dict()
    assert d["request_id"] == "rid-1"
    assert d["session_id"] == "s1"
    assert d["user"] == {"name": "tester"}
    assert "timestamp" in d


def test_context_manager_sync_enter_exit() -> None:
    clear_current_context()
    cm = ContextManager(server=None)
    with cm as ctx:
        assert get_current_context() is ctx
    assert get_current_context() is None


def test_context_manager_create_request_context() -> None:
    cm = ContextManager(server=None)
    ctx = cm.create_request_context(request_data={"method": "tools/call"})
    assert ctx.request_data == {"method": "tools/call"}
    assert ctx.server is None
