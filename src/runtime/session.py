"""
会话管理

提供会话的创建、获取、更新、销毁和过期清理功能。
"""

from __future__ import annotations

import uuid
import time
from typing import Any, Dict, Optional


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
        """创建新会话，返回 session_id"""
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
        """获取会话，若已过期则自动销毁并返回 None"""
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
        """更新会话数据，可选延长超时"""
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
        """销毁指定会话"""
        self._sessions.pop(session_id, None)
        self._session_timeouts.pop(session_id, None)
        return True

    def cleanup_expired_sessions(self) -> int:
        """清理所有过期会话，返回清理数量"""
        expired = [
            sid for sid, exp in self._session_timeouts.items() if time.time() > exp
        ]
        for sid in expired:
            self.destroy_session(sid)
        return len(expired)

    def get_all_sessions(self) -> Dict[str, Dict[str, Any]]:
        """获取所有活跃会话的副本"""
        return self._sessions.copy()


__all__ = [
    "SessionManager",
]
