#!/usr/bin/env python3
"""插件子系统（发现 / 收集 / 注册 / 编排）单测。

覆盖：
- PluginRegistry：注册（同名拒绝/覆盖）、类型化注册、按类型/分类/子分类/tags 过滤查询
- PluginCollector：collect 元数据注入、默认值、get_items 副本、装饰器工厂
- PluginDiscovery：扫描 src.plugins.builtin 真实发现、空路径分支
- PluginManager：initialize 全链路、注册过滤、中间件 wrapper（同步/异步函数）
"""

from __future__ import annotations

from pathlib import Path

from src.constants import PluginType
from src.plugins.collector import PluginCollector
from src.plugins.discovery import PluginDiscovery
from src.plugins.manager import PluginManager
from src.plugins.registry import PluginMetadata, PluginRegistry, RegistryItem
from src.server import MCPServer


def _make_meta(name: str, **kw) -> PluginMetadata:
    return PluginMetadata(name=name, **kw)


# ---------------------------------------------------------------------------
# 注册表
# ---------------------------------------------------------------------------


class TestPluginRegistry:
    def test_register_and_get(self) -> None:
        reg = PluginRegistry("T")

        def add(a: int, b: int) -> int:
            return a + b

        assert (
            reg.register(
                "add",
                add,
                PluginType.TOOL,
                _make_meta("add", description="d"),
                category="math",
                tags=["num"],
            )
            is True
        )
        assert reg.get("add") is add
        item = reg.get_item("add")
        assert item is not None
        assert item.type == PluginType.TOOL
        assert item.metadata.description == "d"
        assert item.category == "math"
        assert item.tags == {"num"}

    def test_get_missing_returns_none(self) -> None:
        reg = PluginRegistry("T")
        assert reg.get("nope") is None
        assert reg.get_item("nope") is None

    def test_duplicate_rejected_and_overwrite(self) -> None:
        reg = PluginRegistry("T")

        def f() -> None:
            return None

        assert reg.register("x", f, PluginType.TOOL, _make_meta("x")) is True
        assert reg.register("x", f, PluginType.TOOL, _make_meta("x")) is False
        assert reg.register("x", f, PluginType.TOOL, _make_meta("x"), overwrite=True) is True

    def test_typed_registers(self) -> None:
        reg = PluginRegistry("T")
        reg.register_tool("t", lambda: None, _make_meta("t"))
        reg.register_resource("r", lambda: None, _make_meta("r"))
        reg.register_prompt("p", lambda: None, _make_meta("p"))
        assert len(reg.get_tools()) == 1
        assert len(reg.get_resources()) == 1
        assert len(reg.get_prompts()) == 1
        assert reg.count() == 3

    def test_query_filters(self) -> None:
        reg = PluginRegistry("T")
        reg.register_tool("t1", lambda: None, _make_meta("t1"), category="math", tags=["fast"])
        reg.register_tool("t2", lambda: None, _make_meta("t2"), category="text", tags=["slow"])
        reg.register_prompt("p1", lambda: None, _make_meta("p1"), category="math")

        # 按类型
        assert len(reg.get_all(PluginType.TOOL)) == 2
        assert len(reg.get_all(PluginType.PROMPT)) == 1
        # 按分类
        assert len(reg.get_all(category="math")) == 2
        # 组合过滤
        assert len(reg.get_all(PluginType.TOOL, category="text")) == 1
        assert len(reg.get_all(PluginType.TOOL, tags=["fast"])) == 1
        # get_all_items 返回 RegistryItem
        items = reg.get_all_items(PluginType.TOOL, category="math")
        assert len(items) == 1
        assert isinstance(items[0], RegistryItem)
        # list_names / count 过滤
        assert reg.list_names(PluginType.TOOL) == ["t1", "t2"]
        assert reg.list_names(category="math") == ["t1", "p1"]
        assert reg.count(PluginType.TOOL) == 2
        assert reg.count(category="text") == 1

    def test_clear(self) -> None:
        reg = PluginRegistry("T")
        reg.register_tool("t", lambda: None, _make_meta("t"))
        reg.clear()
        assert reg.count() == 0


# ---------------------------------------------------------------------------
# 收集器
# ---------------------------------------------------------------------------


class TestPluginCollector:
    def test_collect_injects_metadata(self) -> None:
        col = PluginCollector(PluginType.TOOL)

        def f(a: int, b: int) -> int:
            return a + b

        wrapper = col.collect(f, name="calc", category="math", subcategory="arith", tags=["x"])
        assert wrapper._is_plugin_item is True  # type: ignore[attr-defined]
        assert wrapper._plugin_type == "tool"  # type: ignore[attr-defined]
        assert wrapper._plugin_name == "calc"  # type: ignore[attr-defined]
        assert wrapper._plugin_category == "math"  # type: ignore[attr-defined]
        assert wrapper._plugin_subcategory == "arith"  # type: ignore[attr-defined]
        assert wrapper._plugin_tags == ["x"]  # type: ignore[attr-defined]
        assert wrapper(1, 2) == 3  # 原函数行为保持

        items = col.get_items()
        assert "calc" in items
        assert items["calc"]["doc"] == ""  # 无 docstring
        assert items["calc"]["type"] == PluginType.TOOL

    def test_collect_defaults(self) -> None:
        col = PluginCollector(PluginType.RESOURCE)

        def f() -> None:
            """有文档"""
            return None

        wrapper = col.collect(f)
        assert wrapper._plugin_name == "f"  # type: ignore[attr-defined]
        assert wrapper._plugin_category == "default"  # type: ignore[attr-defined]
        assert col.get_items()["f"]["doc"] == "有文档"

    def test_get_items_returns_copy(self) -> None:
        col = PluginCollector(PluginType.PROMPT)
        col.collect(lambda: None, name="p")
        snapshot = col.get_items()
        snapshot.clear()
        assert len(col.get_items()) == 1

    def test_decorator_factory(self, monkeypatch) -> None:
        import src.plugins.collector as collector_mod

        # 用临时收集器替换全局表，避免污染其他测试
        tmp = {PluginType.TOOL: PluginCollector(PluginType.TOOL)}
        monkeypatch.setattr(collector_mod, "_collectors", tmp)

        @collector_mod.tool(category="math", tags=["demo"])
        def add(a: int, b: int) -> int:
            return a + b

        assert add._is_plugin_item  # type: ignore[attr-defined]
        assert add._plugin_category == "math"  # type: ignore[attr-defined]
        assert add(1, 2) == 3
        assert "add" in tmp[PluginType.TOOL].get_items()


# ---------------------------------------------------------------------------
# 发现器
# ---------------------------------------------------------------------------


class TestPluginDiscovery:
    def test_discover_scans_extensions(self) -> None:
        names = PluginDiscovery().discover()
        assert isinstance(names, list)
        assert len(names) > 0  # src.plugins.builtin 下的 @tool 函数应被发现

    def test_discover_empty_paths(self, monkeypatch) -> None:
        from src.core.config import settings

        monkeypatch.setattr(settings.plugins, "discovery_paths", [])
        assert PluginDiscovery().discover() == []

    def test_scan_module_finds_decorator_items(self) -> None:
        import src.plugins.builtin as ext

        module_path = Path(ext.__file__).parent
        names = PluginDiscovery()._scan_module(ext, module_path)
        assert len(names) > 0


# ---------------------------------------------------------------------------
# 插件管理器
# ---------------------------------------------------------------------------


class TestPluginManager:
    async def test_initialize_registers_extensions(self) -> None:
        server = MCPServer()
        manager = PluginManager(server)
        await manager.initialize()
        assert server.registry.count() > 0

    def test_register_item_writes_registry(self) -> None:
        server = MCPServer()
        manager = PluginManager(server)

        def add(a: int, b: int) -> int:
            return a + b

        info = {"func": add, "doc": "求和", "category": "math", "subcategory": None, "tags": []}
        manager._register_item("tool", "my_add", info)
        assert server.registry.get("my_add") is not None
        assert "my_add" in server.registry.list_names()

    async def test_middleware_wrapper_sync_func(self, monkeypatch) -> None:
        import src.transport.transport as transport_mod

        server = MCPServer()
        manager = PluginManager(server)
        monkeypatch.setattr(transport_mod, "get_request_id", lambda: "rid-1")

        def add(a: int, b: int) -> int:
            return a + b

        wrapper = manager._build_middleware_wrapper(add, "tool", "add2")
        assert await wrapper(2, 3) == 5
        # 可访问原函数
        assert wrapper.__wrapped__ is add

    async def test_middleware_wrapper_async_func(self) -> None:
        server = MCPServer()
        manager = PluginManager(server)

        async def mul(a: int, b: int) -> int:
            return a * b

        wrapper = manager._build_middleware_wrapper(mul, "tool", "mul")
        assert await wrapper(4, 5) == 20
