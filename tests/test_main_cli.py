"""CLI 入口单测：参数解析、无效开关移除、配置更新。"""

from __future__ import annotations

import sys

import pytest

from src.core.config import settings
from src.main import parse_arguments, print_startup_info, update_settings_from_args


def test_parse_arguments_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["x-QiuChi", "--port", "9999"])
    args = parse_arguments()
    assert args.port == 9999
    assert args.transport == settings.mcp.transport
    assert args.host == settings.mcp.host


def test_parse_arguments_rejects_removed_switches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--config / --no-tools / --no-resources / --no-prompts 已被移除。"""
    for flag in ("--config", "--no-tools", "--no-resources", "--no-prompts"):
        monkeypatch.setattr(sys, "argv", ["x-QiuChi", flag])
        with pytest.raises(SystemExit):
            parse_arguments()


def test_update_settings_from_args(monkeypatch: pytest.MonkeyPatch) -> None:
    old = (settings.mcp.port, settings.mcp.host, settings.mcp.server_name)
    try:
        monkeypatch.setattr(
            sys,
            "argv",
            ["x-QiuChi", "--port", "7777", "--host", "127.0.0.1", "--name", "TestSrv"],
        )
        args = parse_arguments()
        update_settings_from_args(args)
        assert settings.mcp.port == 7777
        assert settings.mcp.host == "127.0.0.1"
        assert settings.mcp.server_name == "TestSrv"
    finally:
        settings.mcp.port, settings.mcp.host, settings.mcp.server_name = old


def test_print_startup_info_does_not_raise() -> None:
    """启动信息打印不抛异常（冒烟）。"""
    from types import SimpleNamespace

    from src.main import create_server

    server = create_server("SmokeTest")
    args = SimpleNamespace(
        transport="streamable-http",
        host="0.0.0.0",
        port=8888,
        name="SmokeTest",
        version="0.1.0",
        log_level="INFO",
    )
    print_startup_info(server, args)
