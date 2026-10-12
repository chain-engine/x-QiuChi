"""
真实 MCP 协议测试（官方 mcp client：initialize → tools/list → call_tool）
与传输层认证测试（401 / 200）。

通过子进程启动真实服务（无认证与开认证两种配置），
使用官方 ``streamable_http_client`` 走完整协议握手。
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

ROOT = Path(__file__).resolve().parents[1]

_INIT_PAYLOAD = (
    '{"jsonrpc":"2.0","id":1,"method":"initialize",'
    '"params":{"protocolVersion":"2025-03-26","capabilities":{},'
    '"clientInfo":{"name":"protocol-test","version":"1.0"}}}'
)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_ready(port: int, timeout: float = 30.0) -> None:
    """等待服务器就绪：initialize 返回 200 或 401 均视为已启动。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            r = httpx.post(
                f"http://127.0.0.1:{port}/mcp",
                content=_INIT_PAYLOAD,
                headers={
                    "Accept": "application/json, text/event-stream",
                    "Content-Type": "application/json",
                },
                timeout=2.0,
            )
            if r.status_code in (200, 401):
                return
        except Exception:
            time.sleep(0.25)
    raise RuntimeError(f"server on port {port} did not become ready")


def _spawn_server(port: int, env: dict[str, str] | None = None) -> subprocess.Popen:
    proc_env = {**os.environ, **(env or {})}
    proc = subprocess.Popen(
        [sys.executable, "-m", "src.main", "--port", str(port)],
        cwd=ROOT,
        env=proc_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_ready(port)
    except Exception:
        # 启动失败时给出进程退出码帮助定位
        code = proc.poll()
        raise RuntimeError(f"server did not become ready (exit_code={code})") from None
    return proc


@pytest.fixture(scope="module")
def server_port() -> int:
    """无认证服务（session 级，起一次）。"""
    port = _free_port()
    proc = _spawn_server(port)
    yield port
    proc.terminate()
    proc.wait(timeout=5)


@pytest.fixture(scope="module")
def auth_server_port() -> int:
    """开启传输层认证的服务（AUTH_ENABLED=true）。"""
    port = _free_port()
    proc = _spawn_server(
        port,
        env={
            "AUTH_ENABLED": "true",
            "AUTH_TOKENS": "test-token-123, second-token",
        },
    )
    yield port
    proc.terminate()
    proc.wait(timeout=5)


# ---------------------------------------------------------------
# 真实协议测试（官方 mcp client）
# ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_protocol_initialize_handshake(server_port: int) -> None:
    """initialize 握手：serverInfo 名称与版本（pyproject 单一事实源）。"""
    url = f"http://127.0.0.1:{server_port}/mcp"
    async with (
        streamable_http_client(url) as (read, write, _get_session_id),
        ClientSession(read, write) as session,
    ):
        init = await session.initialize()
        assert init.serverInfo.name == "QiuChi"
        # 未显式设置版本时，mcp SDK 回退为 SDK 自身版本号，非空即可
        assert init.serverInfo.version


@pytest.mark.asyncio
async def test_protocol_tools_list(server_port: int) -> None:
    """tools/list：应列出内置插件注册的 math 工具。"""
    url = f"http://127.0.0.1:{server_port}/mcp"
    async with (
        streamable_http_client(url) as (read, write, _get_session_id),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        tools = await session.list_tools()
        names = [t.name for t in tools.tools]
        # math 工具（src.plugins.builtin.tools.math 注册的 tool 类型插件）
        assert {"add", "subtract", "multiply", "divide", "sqrt"} <= set(names)


@pytest.mark.asyncio
async def test_protocol_call_tool(server_port: int) -> None:
    """tools/call：真实调用 add 工具并校验返回结果。"""
    url = f"http://127.0.0.1:{server_port}/mcp"
    async with (
        streamable_http_client(url) as (read, write, _get_session_id),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        result = await session.call_tool("add", {"a": 1, "b": 2})
        assert result.isError is False
        text = "".join(c.text for c in result.content if getattr(c, "type", "") == "text")
        assert "3" in text


# ---------------------------------------------------------------
# 传输层认证测试（真实 HTTP）
# ---------------------------------------------------------------


def test_auth_rejects_missing_token(auth_server_port: int) -> None:
    """无 Authorization 头 → 401 invalid_token。"""
    r = httpx.post(
        f"http://127.0.0.1:{auth_server_port}/mcp",
        content=_INIT_PAYLOAD,
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        },
        timeout=5.0,
    )
    assert r.status_code == 401
    assert r.json()["error"] == "invalid_token"


def test_auth_rejects_wrong_token(auth_server_port: int) -> None:
    """错误的 Bearer token → 401。"""
    r = httpx.post(
        f"http://127.0.0.1:{auth_server_port}/mcp",
        content=_INIT_PAYLOAD,
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "Authorization": "Bearer wrong-token",
        },
        timeout=5.0,
    )
    assert r.status_code == 401


def test_auth_allows_valid_token(auth_server_port: int) -> None:
    """正确 Bearer token → 200，且握手返回 pyproject 版本。"""
    r = httpx.post(
        f"http://127.0.0.1:{auth_server_port}/mcp",
        content=_INIT_PAYLOAD,
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "Authorization": "Bearer test-token-123",
        },
        timeout=5.0,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["result"]["serverInfo"]["name"] == "QiuChi"
    assert data["result"]["serverInfo"]["version"]
