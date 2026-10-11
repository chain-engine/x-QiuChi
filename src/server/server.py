"""
核心服务器类

企业级 MCP 服务器编排层：组装配置、认证、中间件、插件与传输各组件，
对外暴露统一的 MCPServer 门面。本层不承载具体业务逻辑，
注册流程委托 plugins 层，传输承载委托 transport 层，认证装配委托 core 层。
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any

from mcp.server.fastmcp import FastMCP

from src.constants import ServerState
from src.core.auth import build_auth_from_settings
from src.core.config import settings
from src.core.logger import get_logger
from src.core.middleware import (
    ErrorHandlerMiddleware,
    LoggingMiddleware,
    MiddlewareChain,
)
from src.plugins import PluginManager
from src.plugins.registry import PluginRegistry
from src.server.lifecycle import LifecycleManager
from src.transport import get_transport_config, serve_mcp

logger = get_logger(__name__)


class MCPServer:
    """
    企业级 MCP 服务器（编排门面）

    组装并调度各层组件：
    - 插件注册与发现（委托 PluginManager）
    - 中间件管道（ErrorHandler / Logging）
    - 传输层认证（委托 core.auth，走 mcp SDK 官方 RequireAuthMiddleware）
    - 多传输层承载（Stdio / SSE / Streamable-HTTP，委托 transport 层）
    """

    def __init__(
        self,
        name: str | None = None,
        version: str | None = None,
        **kwargs: Any,
    ):
        self.name = name or settings.mcp.server_name
        self.version = version or settings.mcp.version

        # 认证（传输层 Bearer Token，走 mcp SDK 官方 RequireAuthMiddleware）
        auth_settings, token_verifier = build_auth_from_settings()

        # 创建底层 FastMCP 实例
        self.mcp = FastMCP(
            self.name,
            json_response=settings.mcp.json_response,
            host=settings.mcp.host,
            port=settings.mcp.port,
            auth=auth_settings,
            token_verifier=token_verifier,
            **kwargs,
        )

        # 组件
        self.registry = PluginRegistry("ServerRegistry")
        self.middleware_chain = MiddlewareChain()
        self.plugin_manager = PluginManager(self)
        self.lifecycle = LifecycleManager()

        # 默认中间件：错误处理（最外层）；日志按功能开关挂载
        self.middleware_chain.add(ErrorHandlerMiddleware())
        if settings.features.middleware:
            self.middleware_chain.add(LoggingMiddleware())

        logger.info(f"MCP Server '{self.name}' v{self.version} initialized")

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    async def start(self) -> None:
        if self.lifecycle.get_state() == ServerState.RUNNING:
            logger.warning("Server is already running")
            return

        logger.info(f"Starting MCP Server '{self.name}'...")
        await self.lifecycle.initialize()
        await self.lifecycle.startup()
        await self.plugin_manager.initialize()

        logger.info(f"MCP Server '{self.name}' started")

    async def stop(self) -> None:
        if not self.lifecycle.is_running():
            return

        logger.info(f"Stopping MCP Server '{self.name}'...")
        await self.lifecycle.shutdown()
        logger.info(f"MCP Server '{self.name}' stopped")

    @asynccontextmanager
    async def running(self):
        """运行上下文：进入时启动服务，退出（含异常/取消）时自动关停。

        与 try/finally 语义等价，但把启动/关停配对封装为可复用的
        ``async with`` 用法，测试与脚本可精确控制服务生命周期边界。

        Yields:
            已启动的 MCPServer 实例
        """
        await self.start()
        try:
            yield self
        finally:
            await self.stop()

    # ------------------------------------------------------------------
    # 运行入口
    # ------------------------------------------------------------------
    def run(
        self,
        transport: str | None = None,
        host: str | None = None,
        port: int | None = None,
    ) -> None:
        async def async_run():
            transport_config = get_transport_config(
                transport or settings.mcp.transport,
                host or settings.mcp.host,
                port or settings.mcp.port,
            )

            async with self.running():
                try:
                    await serve_mcp(self.mcp, transport_config)
                except KeyboardInterrupt:
                    logger.info("Server stopped by user")
                except Exception as e:
                    logger.error(f"Server error: {e}")
                    raise

        try:
            asyncio.run(async_run())
        except KeyboardInterrupt:
            logger.info("Server shutdown complete")

    def __repr__(self) -> str:
        return f"MCPServer(name='{self.name}', version='{self.version}', state={self.lifecycle.get_state().value})"


def create_server(
    name: str | None = None,
    version: str | None = None,
    **kwargs: Any,
) -> MCPServer:
    return MCPServer(name, version, **kwargs)
