"""
QiuChi 请求上下文管理

提供请求级别的上下文管理，支持异步环境下的请求隔离。
"""

from __future__ import annotations

import uuid
import time
from contextvars import ContextVar
from typing import Any, Dict, Iterator, Optional, TYPE_CHECKING
from dataclasses import dataclass, field

if TYPE_CHECKING:
    from ..core.server.server import MCPServer


@dataclass
class RequestContext:
    """
    请求上下文

    封装请求的完整信息，包括请求数据、元数据、会话等。
    """

    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    request_data: Dict[str, Any] = field(default_factory=dict)
    response_data: Optional[Dict[str, Any]] = None
    server: Optional["MCPServer"] = None
    session_id: Optional[str] = None
    user: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def update_metadata(self, key: str, value: Any) -> None:
        self.metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        return self.metadata.get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "user": self.user,
            "metadata": self.metadata,
        }


# 全局上下文变量
_current_context: ContextVar[Optional[RequestContext]] = ContextVar("current_context", default=None)


class SessionManager:
    """会话管理器"""

    def __init__(self, default_timeout: int = 3600):
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._session_timeouts: Dict[str, float] = {}
        self._default_timeout = default_timeout

    def create_session(
        self,
        user: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> str:
        session_id = str(uuid.uuid4())
        session_data = {
            "user": user or {},
            "data": data or {},
            "created_at": time.time(),
            "last_accessed": time.time(),
        }
        self._sessions[session_id] = session_data
        self._session_timeouts[session_id] = time.time() + (timeout or self._default_timeout)
        return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        if session_id not in self._sessions:
            return None
        if time.time() > self._session_timeouts.get(session_id, 0):
            self.destroy_session(session_id)
            return None
        self._sessions[session_id]["last_accessed"] = time.time()
        return self._sessions[session_id]

    def update_session(
        self,
        session_id: str,
        data: Optional[Dict[str, Any]] = None,
        user: Optional[Dict[str, Any]] = None,
        extend_timeout: bool = True,
    ) -> bool:
        session = self.get_session(session_id)
        if not session:
            return False
        if data is not None:
            session["data"].update(data)
        if user is not None:
            session["user"].update(user)
        if extend_timeout:
            self._session_timeouts[session_id] = time.time() + self._default_timeout
        return True

    def destroy_session(self, session_id: str) -> bool:
        self._sessions.pop(session_id, None)
        self._session_timeouts.pop(session_id, None)
        return True

    def cleanup_expired_sessions(self) -> int:
        expired = [
            sid for sid, exp in self._session_timeouts.items() if time.time() > exp
        ]
        for sid in expired:
            self.destroy_session(sid)
        return len(expired)

    def get_all_sessions(self) -> Dict[str, Dict[str, Any]]:
        return self._sessions.copy()


# 上下文管理函数
def set_current_context(context: RequestContext) -> Any:
    return _current_context.set(context)


def get_current_context() -> Optional[RequestContext]:
    return _current_context.get()


def reset_current_context(token: Any) -> None:
    _current_context.reset(token)


def clear_current_context() -> None:
    _current_context.set(None)


class ContextManager:
    """
    上下文管理器

    提供：
    - 同步 with 语句：with server.context() as ctx:
    - 异步 async with：async with server.context() as ctx:
    """

    def __init__(self, server: "MCPServer"):
        self.server = server
        self.session_manager = SessionManager()

    def create_request_context(
        self,
        request_data: Dict[str, Any],
        session_id: Optional[str] = None,
    ) -> RequestContext:
        context = RequestContext(
            request_data=request_data,
            server=self.server,
            session_id=session_id,
        )
        if session_id:
            session = self.session_manager.get_session(session_id)
            if session:
                context.user = session.get("user")
        return context

    def process_request(
        self,
        request_data: Dict[str, Any],
        session_id: Optional[str] = None,
    ) -> RequestContext:
        context = self.create_request_context(request_data, session_id)
        set_current_context(context)
        return context

    def finalize_request(self, response_data: Dict[str, Any]) -> None:
        context = get_current_context()
        if context:
            context.response_data = response_data
        clear_current_context()

    # ------------------------------------------------------------------
    # 上下文管理器协议
    # ------------------------------------------------------------------
    def __enter__(self) -> RequestContext:
        self._token = set_current_context(
            RequestContext(server=self.server)
        )
        return _current_context.get()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        reset_current_context(self._token)

    async def __aenter__(self) -> RequestContext:
        # 复用同步 token，ContextVar 跨 await 仍然保持
        self._token = set_current_context(
            RequestContext(server=self.server)
        )
        return _current_context.get()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        reset_current_context(self._token)


__all__ = [
    "RequestContext",
    "SessionManager",
    "ContextManager",
    "get_current_context",
    "set_current_context",
    "reset_current_context",
    "clear_current_context",
]
