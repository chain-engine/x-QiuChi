"""
汉江管理系统 HTTP 转接客户端（适配器核心）

对外提供与汉江管理系统后端（/api/admin/v1/*）交互的异步 HTTP 客户端，
承载"协议转接 + 凭据管理"横切职责：

- 登录链路：GET /auth/public-key 取公钥 → RSA-OAEP(SHA-256) 加密
  ``nonce|timestamp|password`` → POST /auth/login（与汉江 login_crypto 完全对称）
- Token 生命周期：内存缓存 access_token / refresh_token，到期前自动刷新；
  请求遇 401 时 refresh 一次并重试（refresh 失败则重新完整登录）
- 统一响应解析：剥离汉江 ApiResponse 信封（code/message/data/timestamp/request_id），
  向调用方返回业务 data；非 2xx 抛 HanJiangError

本模块不感知 MCP / 插件机制，只做 HTTP + 认证；工具层（auth_tools / user_tools）
负责参数组装与返回格式化。
"""

from __future__ import annotations

import asyncio
import base64
import time
from typing import Any, Final

import httpx
from Crypto.Cipher import PKCS1_OAEP
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA

from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger(__name__)

#: 汉江 admin 域 API 前缀（API_PREFIX=/api + ADMIN_PREFIX=/admin + v1）
#: 接入范围约定：仅 admin 域；开放 API / 开放平台门户不接入
_ADMIN_API_PREFIX: Final[str] = "/api/admin/v1"
#: access_token 剩余有效期小于该值（秒）时提前刷新，避免调用中途过期
_TOKEN_EXPIRY_SLACK_SECONDS: Final[int] = 30


class HanJiangError(Exception):
    """汉江 API 调用错误（非 2xx 响应或网络异常统一包装）。"""

    def __init__(self, message: str, code: int | None = None) -> None:
        """初始化错误。

        Args:
            message: 错误描述（优先取汉江 message，缺失时用 HTTP 状态文本）
            code: HTTP 状态码（网络异常时为 None）
        """
        super().__init__(message)
        self.message = message
        self.code = code


class HanJiangClient:
    """汉江管理系统 HTTP 转接客户端。

    职责：RSA 登录、token 缓存与自动刷新、统一请求封装、错误映射。
    线程安全：token 读写受 asyncio.Lock 保护，并发登录只执行一次。
    """

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        encryption_enabled: bool,
        timeout: float = 30.0,
    ) -> None:
        """初始化客户端。

        Args:
            base_url: 汉江管理系统根地址（如 http://localhost:8000）
            username: 服务凭据账号（汉江管理员）
            password: 服务凭据密码
            encryption_enabled: 是否 RSA-OAEP 加密密码（与汉江 AUTH_ENCRYPTION_ENABLED 一致）
            timeout: 请求超时秒数
        """
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout)
        self._username = username
        self._password = password
        self._encryption_enabled = encryption_enabled
        self._token: dict[str, Any] | None = None
        self._login_lock = asyncio.Lock()

    @classmethod
    def from_settings(cls) -> HanJiangClient:
        """从全局配置构造客户端（配置来源：settings.hanjiang）。"""
        return cls(
            base_url=settings.hanjiang.base_url,
            username=settings.hanjiang.username,
            password=settings.hanjiang.password,
            encryption_enabled=settings.hanjiang.encryption_enabled,
            timeout=settings.hanjiang.timeout,
        )

    # ------------------------------------------------------------------
    # 认证：登录 / 刷新 / 登出
    # ------------------------------------------------------------------

    async def _fetch_public_key(self) -> dict[str, Any]:
        """获取登录公钥与一次性 nonce（登录前必调，nonce 不可复用）。"""
        result: dict[str, Any] = await self.request("GET", "/auth/public-key", auth_required=False)
        return result

    async def _login(self, username: str, password: str) -> dict[str, Any]:
        """执行完整 RSA 登录流程并缓存 token 对。

        Args:
            username: 账号
            password: 明文密码（本函数内完成加密或直通）

        Returns:
            登录响应 data（含 access_token / refresh_token / expires_in）
        """
        public_key_data = await self._fetch_public_key()
        public_key: str = public_key_data["public_key"]
        nonce: str = public_key_data["nonce"]
        timestamp: int = public_key_data["timestamp"]

        # 密文结构 nonce|timestamp|password；时间戳用服务端下发值（±300s 窗口只容网络延迟）
        plaintext = f"{nonce}|{timestamp}|{password}"
        if self._encryption_enabled:
            encrypted_password = self._rsa_encrypt(plaintext, public_key)
        else:
            # 直通模式（汉江 AUTH_ENCRYPTION_ENABLED=false）：encrypted_password 即明文密码
            encrypted_password = password

        body: dict[str, Any] = {
            "username": username,
            "encrypted_password": encrypted_password,
            "nonce": nonce,
        }
        result: dict[str, Any] = await self.request(
            "POST", "/auth/login", json=body, auth_required=False
        )

        self._token = {
            "access_token": result["access_token"],
            "refresh_token": result["refresh_token"],
            "expires_at": time.time() + float(result["expires_in"]),
        }
        logger.info(f"HanJiang 登录成功（账号: {username}）")
        return result

    async def _refresh(self) -> dict[str, Any]:
        """用 refresh_token 换取新令牌对（失败时清空缓存，由调用方重新登录）。"""
        refresh_token = (self._token or {}).get("refresh_token")
        if not refresh_token:
            self._token = None
            raise HanJiangError("无 refresh_token，需要重新登录", code=401)

        result: dict[str, Any] = await self.request(
            "POST",
            "/auth/refresh",
            json={"refresh_token": refresh_token},
            auth_required=False,
        )
        self._token = {
            "access_token": result["access_token"],
            "refresh_token": result["refresh_token"],
            "expires_at": time.time() + float(result["expires_in"]),
        }
        return result

    async def _ensure_token(self) -> str:
        """返回可用 access_token；无缓存或临期时走 登录/刷新 链路（并发只执行一次）。"""
        if self._is_token_valid():
            access_token: str = self._token["access_token"]  # type: ignore[index]
            return access_token

        async with self._login_lock:
            if self._is_token_valid():
                access_token = self._token["access_token"]  # type: ignore[index]
                return access_token
            if self._username and self._password:
                await self._login(self._username, self._password)
            elif self._token and self._token.get("refresh_token"):
                # 无服务凭据但存在旧会话：尝试仅刷新
                await self._refresh()
            else:
                raise HanJiangError(
                    "HanJiang 服务凭据未配置（HANJIANG_USERNAME/PASSWORD）", code=401
                )
            access_token = self._token["access_token"]  # type: ignore[index]
            return access_token

    def _is_token_valid(self) -> bool:
        """token 缓存存在且剩余有效期大于宽松余量。"""
        if not self._token:
            return False
        expires_at = float(self._token.get("expires_at", 0))
        return expires_at > time.time() + _TOKEN_EXPIRY_SLACK_SECONDS

    async def login(self, username: str, password: str) -> dict[str, Any]:
        """显式登录（覆盖服务凭据会话，供 hanjiang_login 工具使用）。

        Args:
            username: 账号
            password: 明文密码

        Returns:
            登录响应 data（含 token 与有效期）
        """
        async with self._login_lock:
            return await self._login(username, password)

    async def logout(self) -> dict[str, Any]:
        """登出：清除汉江 Redis 登录态并清空本地 token 缓存。"""
        result: dict[str, Any] = await self.request("POST", "/auth/logout")
        self._token = None
        return result

    # ------------------------------------------------------------------
    # 统一请求封装
    # ------------------------------------------------------------------

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        data: Any | None = None,
        auth_required: bool = True,
        _retried: bool = False,
    ) -> Any:
        """发送请求并解析汉江统一响应信封，返回业务 data。

        Args:
            method: HTTP 方法（GET/POST）
            path: 相对路径（不含前缀，如 /auth/login）
            params: URL 查询参数
            json: JSON 请求体
            data: 原始请求体（multipart 等）
            auth_required: 是否携带 Bearer（登录/公钥等端点传 False）
            _retried: 内部标记，401 重试仅一次

        Returns:
            汉江响应信封中的 data 字段（dict 或 list）

        Raises:
            HanJiangError: 非 2xx 响应或网络异常
        """
        headers: dict[str, str] = {}
        if auth_required:
            headers["Authorization"] = f"Bearer {await self._ensure_token()}"

        try:
            resp = await self._client.request(
                method,
                f"{_ADMIN_API_PREFIX}{path}",
                headers=headers or None,
                params=params,
                json=json,
                data=data,
            )
        except httpx.HTTPError as e:
            raise HanJiangError(f"请求汉江失败: {e}") from e

        # token 过期 → 刷新/重登一次后重试
        if resp.status_code == 401 and auth_required and not _retried:
            await self._refresh_or_relogin()
            return await self.request(
                method,
                path,
                params=params,
                json=json,
                data=data,
                auth_required=auth_required,
                _retried=True,
            )

        return self._unwrap(resp)

    async def _refresh_or_relogin(self) -> None:
        """401 兜底：先尝试 refresh，失败则用服务凭据重新登录。"""
        try:
            await self._refresh()
        except HanJiangError:
            logger.warning("HanJiang refresh 失败，重新登录")
            self._token = None
            if self._username and self._password:
                await self._login(self._username, self._password)
            else:
                raise

    @staticmethod
    def _unwrap(resp: httpx.Response) -> Any:
        """解析汉江响应：剥离 ApiResponse 信封返回 data；错误响应抛 HanJiangError。"""
        try:
            payload: Any = resp.json()
        except ValueError:
            payload = resp.text

        if not (200 <= resp.status_code < 300):
            message = _extract_error_message(payload, resp)
            raise HanJiangError(message, code=resp.status_code)

        # 统一信封 {code, message, data, timestamp, request_id}；兼容裸数据响应
        if isinstance(payload, dict) and "data" in payload:
            return payload["data"]
        return payload

    @staticmethod
    def _rsa_encrypt(plaintext: str, public_key_pem: str) -> str:
        """RSA-OAEP(SHA-256) 公钥加密 + base64 编码（与汉江 rsa_decrypt 完全对称）。

        Args:
            plaintext: 明文（nonce|timestamp|password）
            public_key_pem: 汉江下发的 RSA 公钥 PEM

        Returns:
            base64 编码的密文
        """
        key = RSA.import_key(public_key_pem)
        cipher = PKCS1_OAEP.new(key, hashAlgo=SHA256)
        return base64.b64encode(cipher.encrypt(plaintext.encode("utf-8"))).decode("ascii")

    # ------------------------------------------------------------------
    # 业务端点（认证域）
    # ------------------------------------------------------------------

    async def get_current_user(self) -> dict[str, Any]:
        """GET /auth/me：当前登录用户资料（仅需登录态）。"""
        result: dict[str, Any] = await self.request("GET", "/auth/me")
        return result

    # ------------------------------------------------------------------
    # 业务端点（用户管理域，payload 由工具层按 schema 组装）
    # ------------------------------------------------------------------

    async def create_user(self, payload: dict[str, Any]) -> Any:
        """POST /users：创建用户。"""
        return await self.request("POST", "/users", json=payload)

    async def list_users(self, params: dict[str, Any]) -> Any:
        """GET /users：分页查询用户列表。"""
        return await self.request("GET", "/users", params=params)

    async def get_user(self, user_id: int) -> Any:
        """GET /users/{id}：查询用户详情。"""
        return await self.request("GET", f"/users/{user_id}")

    async def update_user(self, user_id: int, payload: dict[str, Any]) -> Any:
        """POST /users/{id}/update：更新用户信息。"""
        return await self.request("POST", f"/users/{user_id}/update", json=payload)

    async def update_user_status(self, user_id: int, status: str) -> Any:
        """POST /users/{id}/status：启用/禁用用户。"""
        return await self.request("POST", f"/users/{user_id}/status", json={"status": status})

    async def reset_user_password(self, user_id: int, new_password: str) -> Any:
        """POST /users/{id}/reset-password：重置用户密码。"""
        return await self.request(
            "POST", f"/users/{user_id}/reset-password", json={"new_password": new_password}
        )

    async def delete_user(self, user_id: int) -> Any:
        """POST /users/{id}/delete：软删除用户。"""
        return await self.request("POST", f"/users/{user_id}/delete")

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """关闭底层 HTTP 连接池（优雅停机/测试收尾调用）。"""
        await self._client.aclose()


def _extract_error_message(payload: Any, resp: httpx.Response) -> str:
    """从汉江错误响应中提取可读 message（兼容统一信封 / FastAPI 默认错误）。"""
    if isinstance(payload, dict):
        if message := payload.get("message"):
            return str(message)
        if detail := payload.get("detail"):
            if isinstance(detail, list):  # FastAPI 422 校验错误
                parts = [f"{item.get('loc', '')}: {item.get('msg', '')}" for item in detail]
                return "; ".join(str(p) for p in parts)
            return str(detail)
    return f"HTTP {resp.status_code}: {resp.text[:200]}"


# ------------------------------------------------------------------
# 进程级单例（惰性创建；测试通过 reset_client / monkeypatch 替换）
# ------------------------------------------------------------------

_client_instance: HanJiangClient | None = None


def get_client() -> HanJiangClient:
    """返回进程级 HanJiangClient 单例（首次调用时从全局配置惰性创建）。"""
    global _client_instance
    if _client_instance is None:
        _client_instance = HanJiangClient.from_settings()
    return _client_instance


def reset_client() -> None:
    """重置单例（测试隔离 / 配置变更后重建）。"""
    global _client_instance
    _client_instance = None


__all__ = ["HanJiangClient", "HanJiangError", "get_client", "reset_client"]
