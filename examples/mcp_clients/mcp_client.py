# -*- coding: utf-8 -*-
"""
MCP 示例客户端

零框架依赖（仅 httpx），演示用纯 JSON-RPC 2.0 调用 MCP 服务器的三大原语：
    tools/call · resources/read · prompts/get

运行前提：服务端已启动（默认 http://localhost:8888/mcp）
"""

from __future__ import annotations

import json
import os

import httpx

# ---------------------------------------------------------------------------
# 配置：从项目根 .env 读取（仅填充未设置的键），与配置文件平级独立
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load_env_file(path: str = ".env") -> None:
    env_path = os.path.join(_PROJECT_ROOT, path)
    if not os.path.exists(env_path):
        return
    with open(env_path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


_load_env_file()

BASE_URL = os.getenv("MCP_BASE_URL", "http://localhost:8888").rstrip("/")
MCP_PATH = os.getenv("MCP_PATH", "/mcp")
BEARER_TOKEN = os.getenv("MCP_BEARER_TOKEN", "")

_URL = BASE_URL if BASE_URL.endswith(MCP_PATH) else BASE_URL + (MCP_PATH if MCP_PATH.startswith("/") else f"/{MCP_PATH}")

# ---------------------------------------------------------------------------
# 会话状态：Streamable HTTP 握手后由服务端下发，之后每次请求都要带上
# ---------------------------------------------------------------------------
_session_id: str | None = None
_request_id = 0


def _post(method: str, params: dict | None = None, *, accept_sse: bool = False) -> dict:
    """发送一条 JSON-RPC 请求，返回 result 部分；响应带 error 时抛 RuntimeError。"""
    global _request_id, _session_id
    _request_id += 1

    headers = {"Accept": "application/json, text/event-stream" if accept_sse else "application/json"}
    if BEARER_TOKEN:
        headers["Authorization"] = f"Bearer {BEARER_TOKEN}"
    if _session_id:
        headers["mcp-session-id"] = _session_id

    payload = {"jsonrpc": "2.0", "method": method, "params": params or {}, "id": _request_id}
    resp = httpx.post(_URL, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()

    new_session = resp.headers.get("mcp-session-id")
    if new_session:
        _session_id = new_session

    # 兼容空响应 / SSE 前缀
    text = resp.text.strip()
    if text.startswith("data: "):
        text = text[6:].strip()
    data = json.loads(text) if text else {}
    if "error" in data:
        err = data["error"]
        raise RuntimeError(f"MCP 错误 [{err.get('code')}]: {err.get('message')}")
    return data.get("result", {})


def initialize() -> None:
    """握手：交换协议版本与能力，获取会话 ID。"""
    _post(
        "initialize",
        {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "qiuchi-example-client", "version": "1.0.0"},
        },
        accept_sse=True,
    )
    print(f"已连接 MCP 服务器：{_URL}")


def call(method: str, params: dict | None = None) -> dict:
    """调用任意 MCP 方法（tools/*、resources/*、prompts/* ...）。"""
    return _post(method, params)


# ---------------------------------------------------------------------------
# 测试入口：三大原语各来一发
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    initialize()

    print("\n=== 工具 ===")
    tools = call("tools/list").get("tools", [])
    print(f"tools/list: {[t['name'] for t in tools]}")
    result = call("tools/call", {"name": "add", "arguments": {"a": 1, "b": 2}})
    print(f"tools/call add(1, 2): {json.dumps(result, ensure_ascii=False)}")

    print("\n=== 资源 ===")
    resources = call("resources/list").get("resources", [])
    print(f"resources/list: {[r['uri'] for r in resources]}")
    result = call("resources/read", {"uri": "config://version"})
    print(f"resources/read config://version: {json.dumps(result, ensure_ascii=False)}")

    print("\n=== 提示词 ===")
    prompts = call("prompts/list").get("prompts", [])
    print(f"prompts/list: {[p['name'] for p in prompts]}")
    result = call("prompts/get", {"name": "greeting", "arguments": {"name": "小明"}})
    print(f"prompts/get greeting: {json.dumps(result, ensure_ascii=False)}")

    print("\n测试完成")
