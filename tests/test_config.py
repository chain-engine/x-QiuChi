"""配置模块单测：版本单一事实源、认证/可观测性解析与环境变量覆盖。"""

from __future__ import annotations

from importlib.metadata import version

import pytest

from src.core.config import PACKAGE_VERSION, AuthConfig, OpenTelemetryConfig, Settings


def test_package_version_single_source() -> None:
    """PACKAGE_VERSION 必须等于 pyproject.toml 的 version（唯一事实源）。"""
    assert version("x-QiuChi") == PACKAGE_VERSION
    assert PACKAGE_VERSION == "0.1.0"


def test_mcp_version_uses_package_version() -> None:
    """mcp.version 默认来自 pyproject，而非写死的常量。"""
    from src.core.config import settings

    assert settings.mcp.version == PACKAGE_VERSION


def test_default_auth_disabled_and_tokens_empty() -> None:
    from src.core.config import settings

    assert settings.middleware.auth.enabled is False
    assert settings.middleware.auth.tokens == []


def test_default_telemetry_enabled_console() -> None:
    from src.core.config import settings

    assert settings.telemetry.enabled is True
    assert settings.telemetry.exporter == "console"
    assert settings.telemetry.service_name == "x-QiuChi"


def test_env_override_auth_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    """AUTH_* 环境变量应覆盖 YAML/默认配置。"""
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("AUTH_TOKENS", "token-a, token-b")

    s = Settings()
    assert s.middleware.auth.enabled is True
    assert s.middleware.auth.tokens == ["token-a", "token-b"]


def test_env_override_telemetry(monkeypatch: pytest.MonkeyPatch) -> None:
    """TELEMETRY_* 环境变量应覆盖 YAML/默认配置。"""
    monkeypatch.setenv("TELEMETRY_EXPORTER", "otlp")
    monkeypatch.setenv("TELEMETRY_OTLP_ENDPOINT", "http://localhost:4318/v1/traces")

    s = Settings()
    assert s.telemetry.exporter == "otlp"
    assert s.telemetry.otlp_endpoint == "http://localhost:4318/v1/traces"


def test_auth_config_dataclass_defaults() -> None:
    cfg = AuthConfig()
    assert cfg.enabled is False
    assert cfg.required is True
    assert cfg.tokens == []


def test_telemetry_config_dataclass_defaults() -> None:
    cfg = OpenTelemetryConfig()
    assert cfg.enabled is True
    assert cfg.exporter == "console"
