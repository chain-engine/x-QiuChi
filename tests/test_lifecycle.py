#!/usr/bin/env python3
"""服务器生命周期状态机单测。

覆盖：初始化 / 启动 / 关闭的正常路径、非法状态转换保护、
状态查询（is_running / is_ready / get_state）与重启路径。
"""

import pytest

from src.constants import ServerState
from src.server.lifecycle import LifecycleManager


@pytest.fixture
def lifecycle() -> LifecycleManager:
    return LifecycleManager()


class TestLifecycleManager:
    async def test_initial_state(self, lifecycle: LifecycleManager) -> None:
        assert lifecycle.get_state() == ServerState.UNINITIALIZED
        assert not lifecycle.is_running()
        assert not lifecycle.is_ready()

    async def test_happy_path(self, lifecycle: LifecycleManager) -> None:
        # UNINITIALIZED -> READY
        assert await lifecycle.initialize() is True
        assert lifecycle.get_state() == ServerState.READY
        assert lifecycle.is_ready()
        assert not lifecycle.is_running()

        # READY -> RUNNING
        assert await lifecycle.startup() is True
        assert lifecycle.get_state() == ServerState.RUNNING
        assert lifecycle.is_running()
        assert lifecycle.is_ready()

        # RUNNING -> STOPPED
        assert await lifecycle.shutdown() is True
        assert lifecycle.get_state() == ServerState.STOPPED
        assert not lifecycle.is_running()
        assert not lifecycle.is_ready()

    async def test_startup_from_uninitialized_rejected(self, lifecycle: LifecycleManager) -> None:
        assert await lifecycle.startup() is False
        assert lifecycle.get_state() == ServerState.UNINITIALIZED

    async def test_shutdown_from_uninitialized_rejected(self, lifecycle: LifecycleManager) -> None:
        assert await lifecycle.shutdown() is False
        assert lifecycle.get_state() == ServerState.UNINITIALIZED

    async def test_shutdown_from_ready_rejected(self, lifecycle: LifecycleManager) -> None:
        await lifecycle.initialize()
        assert await lifecycle.shutdown() is False
        assert lifecycle.get_state() == ServerState.READY

    async def test_double_initialize_rejected(self, lifecycle: LifecycleManager) -> None:
        assert await lifecycle.initialize() is True
        assert await lifecycle.initialize() is False
        assert lifecycle.get_state() == ServerState.READY

    async def test_restart_after_stop(self, lifecycle: LifecycleManager) -> None:
        await lifecycle.initialize()
        await lifecycle.startup()
        await lifecycle.shutdown()

        # STOPPED 允许重新 startup（无需重新 initialize）
        assert await lifecycle.startup() is True
        assert lifecycle.is_running()
