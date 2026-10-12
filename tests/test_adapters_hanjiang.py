#!/usr/bin/env python3
"""汉江适配器（HTTP 转接代理）测试。

覆盖：
- HanJiangClient：RSA-OAEP 加密往返、RSA 登录流程（密文结构）、token 缓存复用、
  401→refresh→重试、refresh 失败→重登、错误映射（信封/422/网络）、业务端点、凭据缺失
- 工具层：auth_tools / user_tools 参数组装、返回格式化、错误分支
- 注册集成：import 触发收集后 collector / PluginManager 可见 10 个 hanjiang_* 工具
"""

from __future__ import annotations

import base64
import json
import time
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from Crypto.Cipher import PKCS1_OAEP
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA

from src.adapters.hanjiang import auth_tools, user_tools
from src.adapters.hanjiang.client import HanJiangClient, HanJiangError
from src.constants import PluginType

API = "/api/admin/v1"


# ---------------------------------------------------------------------------
# 工具：构造 Mock 汉江管理系统
# ---------------------------------------------------------------------------


def _make_keypair() -> tuple[RSA.RsaKey, str]:
    """生成测试用 RSA 密钥对，返回 (私钥, 公钥 PEM)。"""
    key = RSA.generate(2048)
    return key, key.public_key().export_key(format="PEM").decode("ascii")


class MockHanJiang:
    """可编程的汉江 Mock 后端（httpx.MockTransport handler）。"""

    def __init__(self, private_key: RSA.RsaKey, public_key_pem: str) -> None:
        self.private_key = private_key
        self.public_key_pem = public_key_pem
        self.public_key_calls: int = 0
        self.login_calls: int = 0
        self.refresh_calls: int = 0
        self.users_calls: int = 0
        self.last_body: dict[str, Any] | None = None
        self.fail_users_once_401: bool = False
        self.refresh_fails: bool = False
        self.plaintext_mode: bool = False

    def _envelope(self, data: Any, code: int = 200) -> dict[str, Any]:
        return {
            "code": code,
            "message": "ok",
            "data": data,
            "timestamp": time.time(),
            "request_id": "rid-test",
        }

    def _error(self, message: str, code: int) -> dict[str, Any]:
        """真实汉江错误响应：message 在顶层（error_response 结构）。"""
        return {
            "code": code,
            "message": message,
            "data": None,
            "timestamp": time.time(),
            "request_id": "rid-test",
        }

    def handler(self) -> Callable[[httpx.Request], httpx.Response]:
        def _handle(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            if path == f"{API}/auth/public-key":
                self.public_key_calls += 1
                return httpx.Response(
                    200,
                    json=self._envelope(
                        {
                            "public_key": self.public_key_pem,
                            "nonce": f"nonce-{self.public_key_calls}",
                            "timestamp": int(time.time()),
                            "expires_in": 300,
                        }
                    ),
                )
            if path == f"{API}/auth/login":
                self.login_calls += 1
                assert request.headers.get("authorization") is None
                self.last_body = json.loads(request.content)
                if self.plaintext_mode:
                    # 直通模式（AUTH_ENCRYPTION_ENABLED=false）：encrypted_password 即明文密码
                    assert self.last_body["encrypted_password"] == "secret-pwd"
                else:
                    cipher = PKCS1_OAEP.new(self.private_key, hashAlgo=SHA256)
                    plain = cipher.decrypt(
                        base64.b64decode(self.last_body["encrypted_password"])
                    ).decode("utf-8")
                    nonce, ts, pwd = plain.split("|", 2)
                    assert nonce == self.last_body["nonce"]
                    assert abs(time.time() - int(ts)) < 600
                    assert pwd == "secret-pwd"
                return httpx.Response(
                    200,
                    json=self._envelope(
                        {
                            "access_token": f"access-{self.login_calls}",
                            "refresh_token": f"refresh-{self.login_calls}",
                            "token_type": "Bearer",
                            "expires_in": 3600,
                        }
                    ),
                )
            if path == f"{API}/auth/refresh":
                self.refresh_calls += 1
                if self.refresh_fails:
                    return httpx.Response(401, json=self._error("refresh 失败", 401))
                return httpx.Response(
                    200,
                    json=self._envelope(
                        {
                            "access_token": f"access-refreshed-{self.refresh_calls}",
                            "refresh_token": f"refresh-new-{self.refresh_calls}",
                            "token_type": "Bearer",
                            "expires_in": 3600,
                        }
                    ),
                )
            if path == f"{API}/auth/me":
                return httpx.Response(
                    200,
                    json=self._envelope(
                        {
                            "id": 1,
                            "username": "admin",
                            "name": "管理员",
                            "role_code": "admin",
                            "status": "active",
                            "permissions": ["USER_VIEW", "USER_CREATE"],
                        }
                    ),
                )
            if path == f"{API}/auth/logout":
                return httpx.Response(200, json=self._envelope({"message": "退出登录成功"}))
            if path == f"{API}/users":
                self.users_calls += 1
                if self.fail_users_once_401 and self.users_calls == 1:
                    return httpx.Response(401, json=self._error("token 过期", 401))
                if request.method == "POST":
                    self.last_body = json.loads(request.content)
                    return httpx.Response(
                        201,
                        json=self._envelope(
                            {"id": 10, "username": self.last_body["username"], "roles": []}, 201
                        ),
                    )
                return httpx.Response(
                    200,
                    json=self._envelope(
                        {
                            "items": [{"id": 1, "username": "admin"}],
                            "total": 1,
                            "page": 1,
                            "page_size": 20,
                            "total_pages": 1,
                        }
                    ),
                )
            if path == f"{API}/users/1":
                return httpx.Response(
                    200, json=self._envelope({"id": 1, "username": "admin", "roles": []})
                )
            if path == f"{API}/users/1/update":
                self.last_body = json.loads(request.content)
                return httpx.Response(200, json=self._envelope({"id": 1, "updated": True}))
            if path == f"{API}/users/1/status":
                self.last_body = json.loads(request.content)
                return httpx.Response(200, json=self._envelope({"id": 1, "status": "inactive"}))
            if path == f"{API}/users/1/reset-password":
                self.last_body = json.loads(request.content)
                return httpx.Response(200, json=self._envelope({"message": "密码重置成功"}))
            if path == f"{API}/users/1/delete":
                return httpx.Response(200, json=self._envelope({"message": "用户删除成功"}))
            # 未模拟路径：403 信封错误（message 在顶层）
            return httpx.Response(403, json=self._error("缺少权限: USER_XXX", 403))

        return _handle


def _make_client(mock: MockHanJiang, *, encryption_enabled: bool = True) -> HanJiangClient:
    """构造绑定 MockTransport 的客户端（绕过真实连接）。"""
    client = HanJiangClient(
        base_url="http://test",
        username="admin",
        password="secret-pwd",
        encryption_enabled=encryption_enabled,
    )
    client._client = httpx.AsyncClient(
        transport=httpx.MockTransport(mock.handler()), base_url="http://test"
    )
    return client


# ---------------------------------------------------------------------------
# RSA 加密原语
# ---------------------------------------------------------------------------


class TestRsaEncrypt:
    def test_rsa_encrypt_roundtrip(self) -> None:
        key, pem = _make_keypair()
        plaintext = "nonce-1|1690000000|secret-pwd"
        encrypted = HanJiangClient._rsa_encrypt(plaintext, pem)
        cipher = PKCS1_OAEP.new(key, hashAlgo=SHA256)
        decrypted = cipher.decrypt(base64.b64decode(encrypted)).decode("utf-8")
        assert decrypted == plaintext


# ---------------------------------------------------------------------------
# HanJiangClient
# ---------------------------------------------------------------------------


class TestHanJiangClient:
    async def test_login_flow_encrypted(self) -> None:
        key, pem = _make_keypair()
        mock = MockHanJiang(key, pem)
        client = _make_client(mock)

        result = await client.login("admin", "secret-pwd")
        assert result["access_token"] == "access-1"
        assert mock.public_key_calls == 1
        assert mock.login_calls == 1
        # 密文由 Mock 侧解密并断言结构（nonce 一致 / 时间窗内 / 密码正确）
        assert mock.last_body is not None
        assert mock.last_body["username"] == "admin"
        await client.close()

    async def test_login_flow_plaintext_when_encryption_disabled(self) -> None:
        key, pem = _make_keypair()
        mock = MockHanJiang(key, pem)
        mock.plaintext_mode = True
        client = _make_client(mock, encryption_enabled=False)

        await client.login("admin", "secret-pwd")
        assert mock.last_body is not None
        # 直通模式：encrypted_password 即明文密码
        assert mock.last_body["encrypted_password"] == "secret-pwd"
        await client.close()

    async def test_ensure_token_reuses_cache(self) -> None:
        key, pem = _make_keypair()
        mock = MockHanJiang(key, pem)
        client = _make_client(mock)

        token1 = await client._ensure_token()
        token2 = await client._ensure_token()
        assert token1 == token2 == "access-1"
        assert mock.login_calls == 1  # 第二次不再登录
        await client.close()

    async def test_401_refresh_and_retry(self) -> None:
        key, pem = _make_keypair()
        mock = MockHanJiang(key, pem)
        mock.fail_users_once_401 = True
        client = _make_client(mock)

        await client._ensure_token()
        data = await client.list_users({"page": 1, "page_size": 20})
        assert mock.users_calls == 2  # 401 后重试一次
        assert mock.refresh_calls == 1
        assert data["items"][0]["username"] == "admin"
        await client.close()

    async def test_refresh_failure_relogin(self) -> None:
        key, pem = _make_keypair()
        mock = MockHanJiang(key, pem)
        mock.fail_users_once_401 = True
        mock.refresh_fails = True
        client = _make_client(mock)

        await client._ensure_token()
        data = await client.list_users({"page": 1})
        assert mock.users_calls == 2
        assert mock.login_calls == 2  # refresh 失败 → 重新登录
        assert data["total"] == 1
        await client.close()

    async def test_error_mapping_envelope(self) -> None:
        key, pem = _make_keypair()
        mock = MockHanJiang(key, pem)
        client = _make_client(mock)

        with pytest.raises(HanJiangError) as exc_info:
            await client.request("GET", "/not-exists")
        assert "缺少权限" in exc_info.value.message
        assert exc_info.value.code == 403
        await client.close()

    async def test_error_mapping_validation_detail(self) -> None:
        client = HanJiangClient(
            base_url="http://test", username="", password="", encryption_enabled=True
        )

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                422,
                json={
                    "detail": [
                        {"loc": ["body", "email"], "msg": "邮箱格式不正确"},
                        {"loc": ["body", "password"], "msg": "密码太短"},
                    ]
                },
            )

        client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="http://test"
        )
        with pytest.raises(HanJiangError) as exc_info:
            await client.request("POST", "/users", json={}, auth_required=False)
        assert "邮箱格式不正确" in exc_info.value.message
        assert "密码太短" in exc_info.value.message
        assert exc_info.value.code == 422
        await client.close()

    async def test_network_error_wrapped(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused")

        client = HanJiangClient(
            base_url="http://test", username="", password="", encryption_enabled=True
        )
        client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="http://test"
        )
        with pytest.raises(HanJiangError) as exc_info:
            await client.request("GET", "/auth/public-key", auth_required=False)
        assert "请求汉江失败" in exc_info.value.message
        await client.close()

    async def test_missing_credentials_raises(self) -> None:
        client = HanJiangClient(
            base_url="http://test", username="", password="", encryption_enabled=True
        )
        with pytest.raises(HanJiangError) as exc_info:
            await client._ensure_token()
        assert "服务凭据未配置" in exc_info.value.message

    async def test_business_endpoints(self) -> None:
        key, pem = _make_keypair()
        mock = MockHanJiang(key, pem)
        client = _make_client(mock)

        me = await client.get_current_user()
        assert me["username"] == "admin"

        created = await client.create_user(
            {"username": "u1", "email": "a@b.c", "password": "x" * 8, "name": "U1", "role_ids": [1]}
        )
        assert created["id"] == 10
        assert mock.last_body is not None
        assert mock.last_body["role_ids"] == [1]

        users = await client.list_users({"page": 1, "page_size": 20})
        assert users["total"] == 1

        detail = await client.get_user(1)
        assert detail["id"] == 1

        updated = await client.update_user(1, {"name": "New"})
        assert updated["updated"] is True
        assert mock.last_body == {"name": "New"}

        status = await client.update_user_status(1, "inactive")
        assert status["status"] == "inactive"

        reset = await client.reset_user_password(1, "new-pwd-123")
        assert "密码重置成功" in reset["message"]

        deleted = await client.delete_user(1)
        assert "用户删除成功" in deleted["message"]
        await client.close()

    async def test_logout_clears_token(self) -> None:
        key, pem = _make_keypair()
        mock = MockHanJiang(key, pem)
        client = _make_client(mock)

        await client._ensure_token()
        assert client._token is not None
        await client.logout()
        assert client._token is None
        await client.close()


# ---------------------------------------------------------------------------
# 工具层
# ---------------------------------------------------------------------------


class _FakeClient:
    """工具测试用桩：记录调用参数并返回固定响应。"""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def _record(self, method: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        self.calls.append((method, args, kwargs))
        return {"ok": True}

    async def login(self, username: str, password: str) -> dict[str, Any]:
        return self._record("login", username, password)

    async def logout(self) -> dict[str, Any]:
        return self._record("logout")

    async def get_current_user(self) -> dict[str, Any]:
        return self._record("get_current_user")

    async def create_user(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._record("create_user", payload)

    async def list_users(self, params: dict[str, Any]) -> dict[str, Any]:
        return self._record("list_users", params)

    async def get_user(self, user_id: int) -> dict[str, Any]:
        return self._record("get_user", user_id)

    async def update_user(self, user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._record("update_user", user_id, payload)

    async def update_user_status(self, user_id: int, status: str) -> dict[str, Any]:
        return self._record("update_user_status", user_id, status)

    async def reset_user_password(self, user_id: int, new_password: str) -> dict[str, Any]:
        return self._record("reset_user_password", user_id, new_password)

    async def delete_user(self, user_id: int) -> dict[str, Any]:
        return self._record("delete_user", user_id)


class TestTools:
    @pytest.fixture(autouse=True)
    def _use_fake_client(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.fake = _FakeClient()
        monkeypatch.setattr(auth_tools, "get_client", lambda: self.fake)
        monkeypatch.setattr(user_tools, "get_client", lambda: self.fake)

    async def test_auth_tools(self) -> None:
        result = await auth_tools.hanjiang_login("admin", "secret")
        assert json.loads(result) == {
            "token_type": "Bearer",
            "expires_in": None,
            "message": "登录成功",
        }
        assert self.fake.calls[0][0] == "login"
        assert self.fake.calls[0][1] == ("admin", "secret")

        await auth_tools.hanjiang_logout()
        assert self.fake.calls[1][0] == "logout"

        result = await auth_tools.hanjiang_session_info()
        assert json.loads(result) == {"ok": True}
        assert self.fake.calls[2][0] == "get_current_user"

    async def test_user_create_tool(self) -> None:
        result = await user_tools.hanjiang_user_create(
            username="u1", email="a@b.c", password="pwd12345", name="U1", role_ids=[1]
        )
        assert json.loads(result) == {"ok": True}
        method, args, _ = self.fake.calls[0]
        assert method == "create_user"
        payload = args[0]
        assert payload["role_ids"] == [1]
        assert "phone" not in payload  # 未提供字段不发送

    async def test_user_list_tool(self) -> None:
        await user_tools.hanjiang_user_list(page=2, page_size=10, keyword="admin", status="active")
        method, args, _ = self.fake.calls[0]
        assert method == "list_users"
        assert args[0] == {"page": 2, "page_size": 10, "keyword": "admin", "status": "active"}

        await user_tools.hanjiang_user_list()
        method, args, _ = self.fake.calls[1]
        assert args[0] == {"page": 1, "page_size": 20}

    async def test_user_update_tool_filters_none(self) -> None:
        await user_tools.hanjiang_user_update(user_id=1, name="New", status="inactive")
        method, args, _ = self.fake.calls[0]
        assert method == "update_user"
        assert args[0] == 1
        assert args[1] == {"name": "New", "status": "inactive"}  # None 字段被过滤

    async def test_user_misc_tools(self) -> None:
        await user_tools.hanjiang_user_get(user_id=1)
        assert self.fake.calls[0][0] == "get_user"

        await user_tools.hanjiang_user_status(user_id=1, status="inactive")
        assert self.fake.calls[1][0] == "update_user_status"

        await user_tools.hanjiang_user_reset_password(user_id=1, new_password="newpwd123")
        assert self.fake.calls[2][0] == "reset_user_password"

        await user_tools.hanjiang_user_delete(user_id=1)
        assert self.fake.calls[3][0] == "delete_user"

    async def test_tool_error_branch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class _FailClient:
            async def login(self, username: str, password: str) -> dict[str, Any]:
                raise HanJiangError("用户名或密码错误", code=401)

        monkeypatch.setattr(auth_tools, "get_client", lambda: _FailClient())
        result = await auth_tools.hanjiang_login("admin", "wrong")
        assert "登录失败" in result
        assert "用户名或密码错误" in result


# ---------------------------------------------------------------------------
# 注册集成
# ---------------------------------------------------------------------------


class TestRegistration:
    async def test_collector_contains_hanjiang_tools(self) -> None:
        # import 已在上层完成（本模块顶部 import src.adapters.hanjiang），断言收集结果
        from src.plugins.collector import get_tool_collector

        names = set(get_tool_collector().get_items().keys())
        expected = {
            "hanjiang_login",
            "hanjiang_logout",
            "hanjiang_session_info",
            "hanjiang_user_create",
            "hanjiang_user_list",
            "hanjiang_user_get",
            "hanjiang_user_update",
            "hanjiang_user_status",
            "hanjiang_user_reset_password",
            "hanjiang_user_delete",
        }
        assert expected.issubset(names)

    async def test_plugin_manager_registers_hanjiang_tools(self) -> None:
        from src.plugins.manager import PluginManager
        from src.server import MCPServer

        server = MCPServer()
        await PluginManager(server).initialize()
        names = server.registry.list_names(PluginType.TOOL)
        assert "hanjiang_login" in names
        assert "hanjiang_user_list" in names
        assert "hanjiang_user_delete" in names
