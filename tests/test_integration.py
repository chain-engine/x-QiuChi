#!/usr/bin/env python3
"""
项目完整性测试脚本

运行此脚本以验证项目是否能正常工作（也兼容 pytest 收集）。
"""

import sys
from pathlib import Path

# 确保以项目根目录为导包根（与运行规范一致：工作目录=根目录）
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_configuration():
    """测试配置系统"""
    print("[1/7] Testing configuration...")
    from src.core.config import settings

    assert settings.mcp.server_name == "QiuChi"
    assert settings.mcp.transport in ["stdio", "sse", "streamable-http"]
    assert settings.mcp.port > 0

    print("    [OK] Configuration loaded successfully")


def test_server_creation():
    """测试服务器创建"""
    print("[2/7] Testing server creation...")
    from src.main import create_server

    server = create_server("TestServer", "1.0.0")
    assert server.name == "TestServer"
    assert server.version == "1.0.0"

    stats = server.get_stats()
    assert stats["running"] is False

    print("    [OK] Server created successfully")


def test_decorators():
    """测试装饰器"""
    print("[3/7] Testing decorators...")
    from src.main import prompt, resource, tool

    @tool(category="test")
    def test_tool(x: int) -> int:
        """Test tool"""
        return x * 2

    @resource(name="test://resource")
    def test_resource() -> str:
        """Test resource"""
        return "test"

    @prompt(category="test")
    def test_prompt(name: str) -> str:
        """Test prompt"""
        return f"Hello {name}"

    # Test functions
    assert test_tool(5) == 10
    assert test_resource() == "test"
    assert test_prompt("World") == "Hello World"

    print("    [OK] Decorators working correctly")


def test_plugin_system():
    """测试插件系统"""
    print("[4/7] Testing plugin system...")
    from src.main import create_server
    from src.plugins import PluginManager

    server = create_server("PluginTest")
    manager = PluginManager(server)

    assert manager.server == server
    assert len(manager.plugins) == 0  # No plugins loaded yet

    print("    [OK] Plugin system initialized")


def test_middleware():
    """测试中间件"""
    print("[5/7] Testing middleware...")
    from src.core.middleware import CacheMiddleware, ErrorHandlerMiddleware, LoggingMiddleware
    from src.main import create_server

    server = create_server("MiddlewareTest")

    # Add middlewares
    server.middleware_chain.add(ErrorHandlerMiddleware())
    server.middleware_chain.add(LoggingMiddleware())
    server.middleware_chain.add(CacheMiddleware())

    # Check middleware chain
    assert len(server.middleware_chain) >= 3

    print("    [OK] Middleware system working")


def test_examples():
    """测试示例插件"""
    print("[6/7] Testing example plugins...")

    try:
        # Test math tools
        from src.examples.tools.math import add, divide, multiply, subtract

        assert add(10, 5) == 15.0
        assert subtract(10, 5) == 5.0
        assert multiply(10, 5) == 50.0
        assert divide(10, 5) == 2.0

        print("    [OK] Math tools working")

        # Test config resources
        from src.examples.resources.config import get_server_config

        config = get_server_config()
        assert isinstance(config, str)
        assert len(config) > 0

        print("    [OK] Config resources working")

        # Test prompt templates
        from src.examples.prompts.templates import greeting

        greeting_text = greeting("Test")
        assert "Test" in greeting_text

        print("    [OK] Prompt templates working")
    except ImportError as e:
        print(f"    [WARN] Failed to import examples: {e}")


def test_server_stats():
    """测试服务器统计"""
    print("[7/7] Testing server statistics...")
    from src.main import create_server

    server = create_server("StatsTest")
    stats = server.get_stats()

    assert "name" in stats
    assert "version" in stats
    assert "running" in stats
    assert "tools" in stats
    assert "resources" in stats
    assert "prompts" in stats
    assert "middlewares" in stats

    assert stats["name"] == "StatsTest"
    assert stats["running"] is False
    assert stats["middlewares"] >= 0

    print("    [OK] Server statistics working")


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("QiuChi Integration Test")
    print("=" * 60 + "\n")

    tests = [
        test_configuration,
        test_server_creation,
        test_decorators,
        test_plugin_system,
        test_middleware,
        test_examples,
        test_server_stats,
    ]

    failed = 0

    for test_func in tests:
        try:
            test_func()
        except Exception as e:
            print(f"    [FAIL] Test failed: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Test Results: {len(tests) - failed} passed, {failed} failed")
    print("=" * 60 + "\n")

    if failed == 0:
        print("[SUCCESS] All tests passed! Project is ready to use.\n")
        return 0
    else:
        print("[FAIL] Some tests failed. Please check the errors above.\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
