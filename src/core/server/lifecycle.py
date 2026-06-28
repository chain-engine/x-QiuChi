"""
QiuChi 服务器生命周期管理

管理服务器的启动、关闭和状态转换。
"""

import asyncio
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from ..logging.logger import get_logger

logger = get_logger(__name__)


class ServerState(str, Enum):
    """服务器状态枚举"""
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class LifecycleManager:
    """
    服务器生命周期管理器

    管理服务器的完整生命周期，包括：
    - 初始化
    - 启动
    - 运行
    - 停止
    - 清理
    """

    def __init__(self):
        self.state = ServerState.UNINITIALIZED
        self._startup_hooks: List[Callable] = []
        self._shutdown_hooks: List[Callable] = []
        self._error_hooks: List[Callable] = []

    def add_startup_hook(self, hook: Callable) -> None:
        """添加启动钩子"""
        self._startup_hooks.append(hook)

    def add_shutdown_hook(self, hook: Callable) -> None:
        """添加关闭钩子"""
        self._shutdown_hooks.append(hook)

    def add_error_hook(self, hook: Callable) -> None:
        """添加错误钩子"""
        self._error_hooks.append(hook)

    async def initialize(self) -> bool:
        """
        初始化服务器

        Returns:
            是否初始化成功
        """
        if self.state != ServerState.UNINITIALIZED:
            logger.warning(f"Cannot initialize from state: {self.state}")
            return False

        try:
            self.state = ServerState.INITIALIZING
            logger.info("Initializing server...")

            # 执行初始化逻辑
            self.state = ServerState.READY
            logger.info("Server initialized successfully")
            return True

        except Exception as e:
            self.state = ServerState.ERROR
            logger.error(f"Failed to initialize server: {e}")
            await self._run_error_hooks(e)
            return False

    async def startup(self) -> bool:
        """
        启动服务器

        Returns:
            是否启动成功
        """
        if self.state not in [ServerState.READY, ServerState.STOPPED]:
            logger.warning(f"Cannot startup from state: {self.state}")
            return False

        try:
            self.state = ServerState.STARTING
            logger.info("Starting server...")

            # 运行启动钩子
            for hook in self._startup_hooks:
                try:
                    if asyncio.iscoroutinefunction(hook):
                        await hook()
                    else:
                        hook()
                except Exception as e:
                    logger.error(f"Startup hook failed: {e}")
                    raise

            self.state = ServerState.RUNNING
            logger.info("Server started successfully")
            return True

        except Exception as e:
            self.state = ServerState.ERROR
            logger.error(f"Failed to start server: {e}")
            await self._run_error_hooks(e)
            return False

    async def shutdown(self) -> bool:
        """
        关闭服务器

        Returns:
            是否关闭成功
        """
        if self.state != ServerState.RUNNING:
            logger.warning(f"Cannot shutdown from state: {self.state}")
            return False

        try:
            self.state = ServerState.STOPPING
            logger.info("Stopping server...")

            # 运行关闭钩子
            for hook in self._shutdown_hooks:
                try:
                    if asyncio.iscoroutinefunction(hook):
                        await hook()
                    else:
                        hook()
                except Exception as e:
                    logger.error(f"Shutdown hook failed: {e}")

            self.state = ServerState.STOPPED
            logger.info("Server stopped successfully")
            return True

        except Exception as e:
            self.state = ServerState.ERROR
            logger.error(f"Failed to stop server: {e}")
            await self._run_error_hooks(e)
            return False

    async def _run_error_hooks(self, error: Exception) -> None:
        """运行错误钩子"""
        for hook in self._error_hooks:
            try:
                if asyncio.iscoroutinefunction(hook):
                    await hook(error)
                else:
                    hook(error)
            except Exception as e:
                logger.error(f"Error hook failed: {e}")

    def is_running(self) -> bool:
        """检查服务器是否正在运行"""
        return self.state == ServerState.RUNNING

    def is_ready(self) -> bool:
        """检查服务器是否就绪"""
        return self.state in [ServerState.READY, ServerState.RUNNING]

    def get_state(self) -> ServerState:
        """获取当前状态"""
        return self.state


__all__ = ["ServerState", "LifecycleManager"]