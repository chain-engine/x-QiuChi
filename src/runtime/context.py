"""
QiuChi 请求上下文管理

提供请求级别的上下文管理，支持异步环境下的请求隔离。
"""

import uuid
import time
from contextvars import ContextVar
from typing import Any, Dict, Optional, TYPE_CHECKING
from dataclasses import dataclass, field

if TYPE_CHECKING:
    from ..core.server.server import MCPServer


@dataclass
class RequestContext:
    """
    请求上下文

    封装请求的完整信息，包括请求数据、元数据、会话等。
    """

    # 请求标识
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    # 时间戳
    timestamp: float = field(default_factory=time.time)
    # 请求数据
    request_data: Dict[str, Any] = field(default_factory=dict)
    # 响应数据
    response_data: Optional[Dict[str, Any]] = None
    # 服务器实例
    server: Optional["MCPServer"] = None
    # 会话ID
    session_id: Optional[str] = None
    # 用户身份
    user: Optional[Dict[str, Any]] = None
    # 自定义元数据
    metadata: Dict[str, Any] = field(default_factory=dict)

    def update_metadata(self, key: str, value: Any) -> None:
        """更新元数据"""
        self.metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """获取元数据"""
        return self.metadata.get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
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
    """
    会话管理器

    管理用户会话，支持会话创建、销毁和查询。
    """

    def __init__(self):
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._session_timeouts: Dict[str, float] = {}

    def create_session(
        self,
        user: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        timeout: int = 3600,  # 默认1小时
    ) -> str:
        """
        创建新会话

        Args:
            user: 用户信息
            data: 会话数据
            timeout: 会话超时时间（秒）

        Returns:
            会话ID
        """
        session_id = str(uuid.uuid4())
        session_data = {
            "user": user or {},
            "data": data or {},
            "created_at": time.time(),
            "last_accessed": time.time(),
        }

        self._sessions[session_id] = session_data
        self._session_timeouts[session_id] = time.time() + timeout

        return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        获取会话

        Args:
            session_id: 会话ID

        Returns:
            会话数据，不存在返回 None
        """
        if session_id not in self._sessions:
            return None

        # 检查是否过期
        if time.time() > self._session_timeouts.get(session_id, 0):
            self.destroy_session(session_id)
            return None

        # 更新最后访问时间
        self._sessions[session_id]["last_accessed"] = time.time()
        return self._sessions[session_id]

    def update_session(
        self,
        session_id: str,
        data: Optional[Dict[str, Any]] = None,
        user: Optional[Dict[str, Any]] = None,
        extend_timeout: bool = True,
    ) -> bool:
        """
        更新会话

        Args:
            session_id: 会话ID
            data: 要更新的数据
            user: 要更新的用户信息
            extend_timeout: 是否延长超时时间

        Returns:
            是否更新成功
        """
        session = self.get_session(session_id)
        if not session:
            return False

        if data is not None:
            session["data"].update(data)

        if user is not None:
            session["user"].update(user)

        if extend_timeout:
            # 延长超时时间（默认延长1小时）
            self._session_timeouts[session_id] = time.time() + 3600

        return True

    def destroy_session(self, session_id: str) -> bool:
        """
        销毁会话

        Args:
            session_id: 会话ID

        Returns:
            是否销毁成功
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
        if session_id in self._session_timeouts:
            del self._session_timeouts[session_id]
        return True

    def cleanup_expired_sessions(self) -> int:
        """
        清理过期会话

        Returns:
            清理的会话数量
        """
        expired = []
        current_time = time.time()

        for session_id, expire_time in self._session_timeouts.items():
            if current_time > expire_time:
                expired.append(session_id)

        for session_id in expired:
            self.destroy_session(session_id)

        return len(expired)

    def get_all_sessions(self) -> Dict[str, Dict[str, Any]]:
        """获取所有会话"""
        return self._sessions.copy()


# 上下文管理函数
def set_current_context(context: RequestContext) -> None:
    """设置当前请求上下文"""
    _current_context.set(context)


def get_current_context() -> Optional[RequestContext]:
    """获取当前请求上下文"""
    return _current_context.get()


def clear_current_context() -> None:
    """清除当前请求上下文"""
    _current_context.set(None)


class ContextManager:
    """
    上下文管理器

    提供上下文管理的高级接口。
    """

    def __init__(self, server: "MCPServer"):
        self.server = server
        self.session_manager = SessionManager()

    def create_request_context(
        self,
        request_data: Dict[str, Any],
        session_id: Optional[str] = None,
    ) -> RequestContext:
        """
        创建请求上下文

        Args:
            request_data: 请求数据
            session_id: 会话ID

        Returns:
            请求上下文实例
        """
        context = RequestContext(
            request_data=request_data,
            server=self.server,
            session_id=session_id,
        )

        # 如果有会话ID，获取会话信息
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
        """
        处理请求并设置当前上下文

        Args:
            request_data: 请求数据
            session_id: 会话ID

        Returns:
            请求上下文实例
        """
        context = self.create_request_context(request_data, session_id)
        set_current_context(context)
        return context

    def finalize_request(self, response_data: Dict[str, Any]) -> None:
        """完成请求处理"""
        context = get_current_context()
        if context:
            context.response_data = response_data
        clear_current_context()