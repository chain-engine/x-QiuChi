"""配置模块单测：版本单一事实源、认证解析与环境变量覆盖。"""

from __future__ import annotations

from importlib.metadata import version

import pytest

from src.core.config import PACKAGE_VERSION, AuthConfig, Settings


def test_package_version_single_source() -> None:
    """PACKAGE_VERSION 必须等于 pyproject.toml 的 version（唯一事实源）。"""
    assert version("x-QiuChi") == PACKAGE_VERSION
    assert PACKAGE_VERSION == "0.1.0"


def test_mcp_version_uses_package_version() -> None:
    """mcp.version 默认来自 pyproject，而非写死的常量。"""
    from src.core.config import settings

    assert settings.mcp.version == PACKAGE_VERSION


def test_default_auth_disabled_and_tokens_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """代码默认值：认证关闭、无 token（排除本机 config.yaml 与 .env 的干扰）。"""
    monkeypatch.delenv("AUTH_ENABLED", raising=False)
    monkeypatch.delenv("AUTH_TOKENS", raising=False)

    s = Settings(config_file="nonexistent-config.yaml")
    assert s.middleware.auth.enabled is False
    assert s.middleware.auth.tokens == []


def test_env_override_auth_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    """AUTH_* 环境变量应覆盖 YAML/默认配置。"""
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("AUTH_TOKENS", "token-a, token-b")

    s = Settings()
    assert s.middleware.auth.enabled is True
    assert s.middleware.auth.tokens == ["token-a", "token-b"]


def test_auth_config_dataclass_defaults() -> None:
    cfg = AuthConfig()
    assert cfg.enabled is False
    assert cfg.tokens == []
