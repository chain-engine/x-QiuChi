"""
服务器生命周期管理

管理服务器的启动、关闭和状态转换。
"""

from src.constants import ServerState
from src.core.logger import get_logger

logger = get_logger(__name__)


class LifecycleManager:
    """
    服务器生命周期管理器

    显式状态机：管理服务器的初始化、启动、运行、停止，
    支持状态查询与非法转换保护。
    """

    def __init__(self):
        self.state = ServerState.UNINITIALIZED

    async def initialize(self) -> bool:
        """
        初始化服务器

        Returns:
            是否初始化成功
        """
        if self.state != ServerState.UNINITIALIZED:
            logger.warning(f"Cannot initialize from state: {self.state}")
            return False

        self.state = ServerState.INITIALIZING
        logger.info("Initializing server...")
        self.state = ServerState.READY
        logger.info("Server initialized successfully")
        return True

    async def startup(self) -> bool:
        """
        启动服务器

        Returns:
            是否启动成功
        """
        if self.state not in [ServerState.READY, ServerState.STOPPED]:
            logger.warning(f"Cannot startup from state: {self.state}")
            return False

        self.state = ServerState.STARTING
        logger.info("Starting server...")
        self.state = ServerState.RUNNING
        logger.info("Server started successfully")
        return True

    async def shutdown(self) -> bool:
        """
        关闭服务器

        Returns:
            是否关闭成功
        """
        if self.state != ServerState.RUNNING:
            logger.warning(f"Cannot shutdown from state: {self.state}")
            return False

        self.state = ServerState.STOPPING
        logger.info("Stopping server...")
        self.state = ServerState.STOPPED
        logger.info("Server stopped successfully")
        return True

    def is_running(self) -> bool:
        """检查服务器是否正在运行"""
        return self.state == ServerState.RUNNING

    def is_ready(self) -> bool:
        """检查服务器是否就绪"""
        return self.state in [ServerState.READY, ServerState.RUNNING]

    def get_state(self) -> ServerState:
        """获取当前状态"""
        return self.state


__all__ = ["LifecycleManager"]
