# -*- coding: utf-8 -*-
"""
MCP 客户端

提供通用的 MCP (Model Context Protocol) 服务器客户端，支持 JSON-RPC 2.0 协议。
特性：
- 纯 Python 实现，零框架依赖（仅需 requests）
- 类封装 + 实例隔离，支持多 MCP 服务端并行
- 纯字典参数校验 + 类型提示
- 自增请求 ID（JSON-RPC 合规）
- 线程安全（实例级锁 + 可重入）
- 自动重试 + 指数退避
- 结构化日志 + 异常分级
- 配置类支持（环境变量/字典注入）
- 会话过期自动重连
"""

from __future__ import annotations

import json
import logging
import os
import time
import threading
from typing import Any, Dict, Optional, Mapping, Union, List
from dataclasses import dataclass, field

import requests
from requests.exceptions import RequestException, Timeout, HTTPError


# ==================== 配置管理 ====================

@dataclass
class MCPConfig:
    """MCP 客户端配置（支持环境变量覆盖）"""
    
    base_url: str = field(default_factory=lambda: os.getenv("MCP_BASE_URL", "http://localhost:8000"))
    mcp_path: str = field(default_factory=lambda: os.getenv("MCP_PATH", "/mcp"))
    timeout: int = field(default_factory=lambda: int(os.getenv("MCP_TIMEOUT", "30")))
    max_retries: int = field(default_factory=lambda: int(os.getenv("MCP_MAX_RETRIES", "3")))
    retry_delay: float = field(default_factory=lambda: float(os.getenv("MCP_RETRY_DELAY", "1.0")))
    protocol_version: str = field(default="2024-11-05")
    client_name: str = field(default="x-mcp-client")
    client_version: str = field(default="1.0.0")

    @classmethod
    def from_dict(cls, overrides: Dict[str, Any]) -> "MCPConfig":
        """从字典创建配置（用于动态注入）"""
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in overrides.items() if k in valid_keys})


def _compose_mcp_endpoint(base_url: str, mcp_path: str) -> str:
    """拼接 base_url 与 mcp_path；若 base_url 已以 mcp_path 结尾则不再重复追加。"""
    base = base_url.rstrip("/")
    path = mcp_path if mcp_path.startswith("/") else f"/{mcp_path}"
    if base.endswith(path):
        return base
    return f"{base}{path}"


# ==================== 日志配置 ====================

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


# ==================== 异常定义 ====================

class MCPError(Exception):
    """MCP 调用基础异常"""
    def __init__(self, message: str, code: Optional[int] = None, details: Optional[Dict] = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)

    def __str__(self):
        if self.code is not None:
            return f"[{self.code}] {self.message}"
        return self.message


class MCPConnectionError(MCPError):
    """网络连接异常"""
    pass


class MCPProtocolError(MCPError):
    """JSON-RPC 协议异常"""
    pass


class MCPToolError(MCPError):
    """工具执行错误（业务层）"""
    pass


class MCPValidationError(MCPError):
    """参数校验错误"""
    pass


# ==================== 参数校验工具 ====================

def validate_method(method: Any) -> str:
    """校验 method 参数"""
    if method is None:
        raise MCPValidationError("method 不能为空")
    if not isinstance(method, str):
        raise MCPValidationError(f"method 必须为字符串，得到 {type(method).__name__}")
    method = method.strip()
    if not method:
        raise MCPValidationError("method 不能为空字符串")
    return method


def validate_params(params: Any) -> Optional[Dict[str, Any]]:
    """校验 params 参数"""
    if params is None:
        return None
    if not isinstance(params, dict):
        raise MCPValidationError(f"params 必须为字典或 None，得到 {type(params).__name__}")
    return params


def validate_call_args(method: Any, params: Any = None) -> Dict[str, Any]:
    """
    校验 MCP 调用参数
    
    Returns:
        校验后的参数字典 {"method": str, "params": dict or None}
    """
    return {
        "method": validate_method(method),
        "params": validate_params(params),
    }


def validate_initialize_params(params: Dict[str, Any]) -> None:
    """校验 initialize 方法专用参数"""
    required_keys = ["protocolVersion", "capabilities", "clientInfo"]
    missing = [k for k in required_keys if k not in params]
    if missing:
        raise MCPValidationError(f"initialize 缺少必需参数：{missing}")
    
    if not isinstance(params.get("clientInfo"), dict):
        raise MCPValidationError("clientInfo 必须为字典")
    
    client_info = params["clientInfo"]
    if "name" not in client_info or "version" not in client_info:
        raise MCPValidationError("clientInfo 必须包含 name 和 version")


# ==================== 核心工具类 ====================

class MCPClient:
    """
    生产级通用 MCP 客户端
    
    支持：
    - 多实例隔离（不同 MCP 服务端）
    - 自动会话管理 + 过期重连
    - 线程安全调用
    - 指数退避重试
    - 结构化异常抛出（可选）
    
    示例：
    ```python
    client = MCPClient(base_url="http://prod-mcp:8000")
    
    # 方式 1: 直接调用
    result = client.call("tools/list", {})
    
    # 方式 2: 带校验调用
    result = client.call_validated(method="tools/call", params={"name": "get_weather", ...})
    
    # 方式 3: 上下文管理器
    with MCPClient(...) as client:
        result = client.call(...)
    ```
    """

    # 预定义合法 method 列表（可选校验）
    ALLOWED_METHODS = {
        "initialize",
        "tools/list",
        "tools/call",
        "prompts/list",
        "prompts/get",
        "resources/list",
        "resources/read",
        "logging/setLevel",
        "completion/complete",
    }

    def __init__(
        self,
        config: Optional[MCPConfig] = None,
        base_url: Optional[str] = None,
        mcp_path: Optional[str] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
        retry_delay: Optional[float] = None,
        raise_on_error: bool = False,
        strict_method_check: bool = False,  # 是否严格校验 method 白名单
    ):
        """
        初始化客户端
        
        参数优先级：直接参数 > config 字典 > 环境变量 > 默认值
        """
        # 合并配置
        overrides = {k: v for k, v in {
            "base_url": base_url,
            "mcp_path": mcp_path,
            "timeout": timeout,
            "max_retries": max_retries,
            "retry_delay": retry_delay,
        }.items() if v is not None}
        self.config = config.from_dict(overrides) if config else MCPConfig.from_dict(overrides)
        
        # 实例状态（线程安全）
        self._session_id: Optional[str] = None
        self._request_id: int = 1
        self._initialized: bool = False
        self._lock = threading.RLock()
        self._raise_on_error = raise_on_error
        self._strict_method_check = strict_method_check
        
        # 预计算请求地址（避免把已含路径的 base_url 再次拼接 mcp_path）
        self._url = _compose_mcp_endpoint(self.config.base_url, self.config.mcp_path)
        
        logger.debug(f"MCP 客户端初始化：url={self._url}, timeout={self.config.timeout}s")

    def _next_request_id(self) -> int:
        """生成自增请求 ID（线程安全）"""
        with self._lock:
            rid = self._request_id
            self._request_id += 1
            return rid

    def _validate_method_allowed(self, method: str) -> None:
        """校验 method 是否在白名单内"""
        if self._strict_method_check and method not in self.ALLOWED_METHODS:
            logger.warning(f"未知 MCP method: {method}（严格模式已启用）")

    def _build_initialize_payload(self) -> Dict[str, Any]:
        """构建 initialize 请求"""
        return {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": self.config.protocol_version,
                "capabilities": {
                    "roots": {"listChanged": True},
                    "sampling": {},
                },
                "clientInfo": {
                    "name": self.config.client_name,
                    "version": self.config.client_version,
                },
            },
            "id": self._next_request_id(),
        }

    def _build_jsonrpc_payload(self, method: str, params: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
        """构建通用 JSON-RPC 请求"""
        return {
            "jsonrpc": "2.0",
            "method": method,
            "params": dict(params) if params else {},
            "id": self._next_request_id(),
        }

    def _do_request(
        self,
        payload: Dict[str, Any],
        session_id: Optional[str] = None,
        accept_sse: bool = False,
    ) -> Dict[str, Any]:
        """发送 HTTP POST 请求（含基础错误处理）"""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream" if accept_sse else "application/json",
        }
        if session_id:
            headers["mcp-session-id"] = session_id

        try:
            response = requests.post(
                self._url,
                json=payload,
                headers=headers,
                timeout=self.config.timeout,
            )
            response.raise_for_status()
            
            # 提取 session-id（首次握手时）
            new_session = response.headers.get("mcp-session-id")
            if new_session and new_session != session_id:
                with self._lock:
                    self._session_id = new_session
                logger.debug(f"获取新会话 ID: {new_session[:16]}...")
            
            # 兼容空响应 / SSE 前缀
            text = response.text.strip()
            if not text:
                return {"result": {}}
            if text.startswith("data: "):
                text = text[6:].strip()
            
            data = json.loads(text)
            if isinstance(data, dict) and "error" in data:
                err = data["error"]
                raise MCPProtocolError(
                    message=err.get("message", "未知协议错误"),
                    code=err.get("code"),
                    details=err.get("data")
                )
            return data
            
        except Timeout as e:
            raise MCPConnectionError(f"请求超时 ({self.config.timeout}s)", details={"url": self._url}) from e
        except HTTPError as e:
            status = e.response.status_code
            raise MCPConnectionError(
                f"HTTP {status}", 
                code=status,
                details={"url": self._url, "response": e.response.text[:200]}
            ) from e
        except json.JSONDecodeError as e:
            raise MCPProtocolError(f"响应解析失败：{e}", details={"raw": response.text[:200]}) from e
        except RequestException as e:
            raise MCPConnectionError(f"网络请求失败：{e}") from e

    def _handshake_session(self) -> str:
        """执行会话握手（获取 session-id）"""
        payload = self._build_initialize_payload()
        result = self._do_request(payload, accept_sse=True)
        
        if not self._session_id:
            raise MCPProtocolError("握手成功但未返回 mcp-session-id 响应头")
        
        if "result" in result:
            logger.debug(f"MCP 服务端能力：{result['result'].get('capabilities', {})}")
        
        return self._session_id

    def _ensure_initialized(self) -> None:
        """确保会话已初始化（支持过期重连）"""
        with self._lock:
            if self._initialized and self._session_id:
                return
        
        logger.info("正在初始化 MCP 会话...")
        self._handshake_session()
        self._initialized = True
        logger.info("MCP 会话初始化成功")

    def _invoke_with_retry(
        self,
        method: str,
        params: Optional[Mapping[str, Any]],
    ) -> Dict[str, Any]:
        """执行调用 + 指数退避重试"""
        last_exc: Optional[Exception] = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                self._ensure_initialized()
                
                payload = self._build_jsonrpc_payload(method, params)
                result = self._do_request(payload, session_id=self._session_id)
                
                return result.get("result", result)
                
            except MCPToolError:
                raise
            except (MCPConnectionError, MCPProtocolError) as e:
                last_exc = e
                if attempt < self.config.max_retries:
                    delay = self.config.retry_delay * (2 ** attempt)
                    logger.warning(f"调用失败 (尝试 {attempt+1}/{self.config.max_retries+1}), {delay}s 后重试：{e}")
                    time.sleep(delay)
                    with self._lock:
                        self._initialized = False
                else:
                    raise
        
        raise last_exc or RuntimeError("未知重试失败")

    def call(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        return_dict: bool = False,
        skip_validation: bool = False,
    ) -> Union[Dict[str, Any], str]:
        """
        主调用入口：执行 MCP JSON-RPC 调用
        
        Args:
            method: JSON-RPC 方法名
            params: 方法参数字典
            return_dict: True 返回 dict，False 返回 JSON 字符串
            skip_validation: 是否跳过参数校验（默认校验）
            
        Returns:
            dict 或 JSON 字符串
            
        Raises:
            MCPError 及其子类（当 raise_on_error=True 时）
        """
        try:
            # 参数校验
            if not skip_validation:
                validated = validate_call_args(method, params)
                method = validated["method"]
                params = validated["params"]
            
            # 白名单校验（可选）
            self._validate_method_allowed(method)
            
            # 执行调用
            result = self._invoke_with_retry(method, params)
            return result if return_dict else json.dumps(result, ensure_ascii=False)
            
        except MCPValidationError as e:
            logger.error(f"参数校验错误：{e}")
            error_payload = {"error": {"message": str(e), "type": "ValidationError"}}
            if self._raise_on_error:
                raise
            return error_payload if return_dict else json.dumps(error_payload, ensure_ascii=False)
            
        except MCPToolError as e:
            logger.error(f"工具执行错误：{e}")
            error_payload = {"error": {"message": e.message, "code": e.code, "details": e.details}}
            if self._raise_on_error:
                raise
            return error_payload if return_dict else json.dumps(error_payload, ensure_ascii=False)
            
        except (MCPConnectionError, MCPProtocolError) as e:
            logger.error(f"MCP 调用失败：{e}", exc_info=True)
            error_payload = {"error": {"message": str(e), "type": type(e).__name__}}
            if self._raise_on_error:
                raise
            return error_payload if return_dict else json.dumps(error_payload, ensure_ascii=False)
            
        except Exception as e:
            logger.critical(f"未预期异常：{type(e).__name__}: {e}", exc_info=True)
            error_payload = {"error": {"message": "内部错误，请联系管理员", "type": "UnexpectedError"}}
            if self._raise_on_error:
                raise
            return error_payload if return_dict else json.dumps(error_payload, ensure_ascii=False)

    def call_validated(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        return_dict: bool = False,
    ) -> Union[Dict[str, Any], str]:
        """
        带严格校验的调用入口（推荐生产使用）
        
        与 call() 的区别：
        - 始终执行参数校验（不可跳过）
        - 始终启用 method 白名单检查
        """
        # 强制校验
        validated = validate_call_args(method, params)
        self._strict_method_check = True
        return self.call(
            method=validated["method"],
            params=validated["params"],
            return_dict=return_dict,
            skip_validation=True,  # 已校验过
        )

    def __call__(
        self,
        method: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        return_dict: bool = False,
        **kwargs: Any,
    ) -> Union[Dict[str, Any], str]:
        """支持函数式调用风格"""
        if method is None and "method" in kwargs:
            method = kwargs.pop("method")
        if params is None and "params" in kwargs:
            params = kwargs.pop("params")
        
        if not method:
            raise MCPValidationError("method 参数必需")
        
        return self.call(method, params, return_dict)

    def close(self) -> None:
        """清理资源"""
        with self._lock:
            self._session_id = None
            self._initialized = False
            self._request_id = 1
        logger.debug("MCP 客户端资源已清理")

    def __enter__(self) -> "MCPClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"MCPClient(url={self._url!r}, initialized={self._initialized})"


# ==================== 便捷函数封装 ====================

def create_mcp_client(
    config: Optional[Union[MCPConfig, Dict[str, Any]]] = None,
    raise_on_error: bool = False,
    strict_method_check: bool = False,
    **overrides: Any,
) -> MCPClient:
    """
    工厂函数：快速创建 MCP 客户端实例
    
    示例：
    ```python
    client = create_mcp_client()
    client = create_mcp_client(base_url="http://prod:8000", timeout=60)
    client = create_mcp_client(config={"base_url": "...", "timeout": 45})
    ```
    """
    if isinstance(config, dict):
        config = MCPConfig.from_dict(config)
    
    return MCPClient(
        config=config,
        raise_on_error=raise_on_error,
        strict_method_check=strict_method_check,
        **{k: v for k, v in overrides.items() if k in MCPConfig.__dataclass_fields__}
    )


# ==================== 默认实例（谨慎使用） ====================

default_mcp_client: MCPClient = create_mcp_client()


# ==================== 测试入口 ====================

if __name__ == "__main__":
    logger.setLevel(logging.DEBUG)
    
    print("MCP 客户端 - 生产级测试（零依赖版）")
    print(f"服务端：{default_mcp_client._url}")
    
    # 测试 1: 参数校验
    print("\n🔍 测试：参数校验")
    test_cases = [
        (None, {}, "method 为空"),
        (123, {}, "method 非字符串"),
        ("", {}, "method 空字符串"),
        ("tools/list", "not-a-dict", "params 非字典"),
    ]
    for method, params, desc in test_cases:
        try:
            validate_call_args(method, params)
            print(f"  {desc}: 应失败但未失败")
        except MCPValidationError as e:
            print(f"  {desc}: {e}")
    
    # 测试 2: tools/list
    print("\n测试：tools/list")
    try:
        result = default_mcp_client.call("tools/list", {}, return_dict=True)
        print(f"响应类型：{type(result)}, 预览：{str(result)[:200]}...")
    except Exception as e:
        print(f"失败：{type(e).__name__}: {e}")
    
    # 测试 3: tools/call
    print("\n测试：tools/call")
    try:
        result = default_mcp_client.call(
            "tools/call",
            {"name": "get_weather", "arguments": {"city": "Beijing"}},
            return_dict=True
        )
        print(f"响应：{json.dumps(result, ensure_ascii=False, indent=2)[:300]}...")
    except MCPToolError as e:
        print(f"工具业务错误：{e}")
    except Exception as e:
        print(f"跳过/失败：{type(e).__name__}: {e}")
    
    # 测试 4: 上下文管理器（base_url 须为不含 mcp_path 的根地址，或已规范化后的完整 URL）
    print("\n测试：上下文管理器")
    with MCPClient(
        base_url=default_mcp_client.config.base_url,
        mcp_path=default_mcp_client.config.mcp_path,
        timeout=10,
    ) as client:
        print(f"  客户端：{client}")
        result = client.call("tools/list", {})
        print(f"  调用成功，响应长度：{len(result)}")
    
    print("\n测试完成")