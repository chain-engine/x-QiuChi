#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
应用配置管理模块

支持从环境变量和 YAML 配置文件读取配置，使用 dataclass 描述各配置段。
配置优先级：环境变量 > YAML 配置文件 > 代码默认值。

Usage:
    from src.core.config import settings
    port = settings.mcp.port
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

import yaml

from src.constants.enums import LogLevel, LogOutput, TransportType

# 常量内联（避免跨包循环导入）
DEFAULT_CONFIG_FILE: str = "config.yaml"
ENV_DEVELOPMENT: str = "development"
ENV_PRODUCTION: str = "production"
ENV_TESTING: str = "testing"


# ============================================================
# 项目根目录
# ============================================================

PROJECT_ROOT: Path = Path(__file__).resolve().parents[3]


# ============================================================
# 辅助函数
# ============================================================

def _to_bool(value: Any) -> bool:
    """将值转换为布尔类型。"""
    if isinstance(value, bool):
        return value
    return str(value).lower() in ("true", "1", "yes", "on")


def _to_int(value: Any, default: int = 0) -> int:
    """将值转换为整数类型。"""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _to_float(value: Any, default: float = 0.0) -> float:
    """将值转换为浮点类型。"""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _find_project_root() -> Path:
    """查找项目根目录。"""
    return PROJECT_ROOT


# ============================================================
# Dataclass 配置段
# ============================================================

@dataclass
class MCPConfig:
    """MCP 服务器配置。"""
    server_name: str = "QiuChi"
    version: str = "1.0.0"
    transport: str = TransportType.STREAMABLE_HTTP.value
    host: str = "0.0.0.0"
    port: int = 8000
    json_response: bool = True


@dataclass
class LoggingConfig:
    """日志配置。"""
    level: str = LogLevel.INFO.value
    output: str = LogOutput.BOTH.value
    file_path: str = "logs/x-QiuChi_{time:YYYY-MM-DD-HH}.log"
    rotation: str = "1 hour"
    retention: str = "7 days"
    format: str = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{file.name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )


@dataclass
class FeaturesConfig:
    """功能开关配置。"""
    tools: bool = True
    resources: bool = True
    prompts: bool = True
    middleware: bool = True
    cache: bool = False


@dataclass
class PluginConfig:
    """插件配置。"""
    auto_discovery: bool = True
    discovery_paths: list[str] = field(default_factory=lambda: ["plugins", "examples"])
    enabled_plugins: list[str] = field(default_factory=list)
    disabled_plugins: list[str] = field(default_factory=list)


@dataclass
class AuthConfig:
    """认证配置。"""
    enabled: bool = False
    required: bool = True
    exempt_methods: list[str] = field(default_factory=list)


@dataclass
class ErrorHandlerConfig:
    """错误处理中间件配置。"""
    include_traceback: bool = False


@dataclass
class LoggingMiddlewareConfig:
    """日志中间件配置。"""
    log_request: bool = True
    log_response: bool = True


@dataclass
class CacheConfig:
    """缓存配置。"""
    enabled: bool = False
    default_ttl: int = 300
    max_size: int = 1000


@dataclass
class MiddlewareConfig:
    """中间件配置。"""
    error_handler: ErrorHandlerConfig = field(default_factory=ErrorHandlerConfig)
    logging: LoggingMiddlewareConfig = field(default_factory=LoggingMiddlewareConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)


# ============================================================
# 环境变量 → YAML 配置段 映射
# ============================================================

_ENV_SECTION_MAP: dict[str, tuple[str, list[str]]] = {
    "mcp": ("MCP_", ["server_name", "version", "transport", "host", "port", "json_response"]),
    "logging": ("LOGGING_", ["level", "output", "file_path", "rotation", "retention", "format"]),
    "features": ("FEATURES_", ["tools", "resources", "prompts", "middleware", "cache"]),
    "plugins": ("PLUGIN_", ["auto_discovery"]),
    "middleware.auth": ("AUTH_", ["enabled", "required"]),
}


# ============================================================
# 核心配置类
# ============================================================

class Settings:
    """应用全局配置类。

    配置加载优先级（从高到低）：
        1. 环境变量
        2. YAML 配置文件（config.yaml）
        3. 代码中的默认值

    Attributes:
        app_env: 当前运行环境
        mcp: MCP 服务器配置
        logging: 日志配置
        features: 功能开关配置
        plugins: 插件配置
        middleware: 中间件配置
    """

    def __init__(self, config_file: str | None = None) -> None:
        """初始化配置。"""
        self._config_file = config_file or DEFAULT_CONFIG_FILE
        self._config: dict[str, Any] = self._load_config()
        self._parse_config()

    # ----------------------------------------------------------
    # 配置加载
    # ----------------------------------------------------------

    def _load_config(self) -> dict[str, Any]:
        """加载配置，优先级：环境变量 > YAML 文件 > 默认值。"""
        config = self._get_default_config()
        self._load_from_yaml(config)
        self._load_from_env(config)
        return config

    def _get_default_config(self) -> dict[str, Any]:
        """返回所有配置段的代码默认值。"""
        return {
            "app_env": ENV_DEVELOPMENT,
            "mcp": {
                "server_name": "QiuChi",
                "version": "1.0.0",
                "transport": TransportType.STREAMABLE_HTTP.value,
                "host": "0.0.0.0",
                "port": 8000,
                "json_response": True,
            },
            "logging": {
                "level": LogLevel.INFO.value,
                "output": LogOutput.BOTH.value,
                "file_path": "logs/x-QiuChi_{time:YYYY-MM-DD-HH}.log",
                "rotation": "1 hour",
                "retention": "7 days",
                "format": (
                    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                    "<level>{level: <8}</level> | "
                    "<cyan>{file.name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
                    "<level>{message}</level>"
                ),
            },
            "features": {
                "tools": True,
                "resources": True,
                "prompts": True,
                "middleware": True,
                "cache": False,
            },
            "plugins": {
                "auto_discovery": True,
                "discovery_paths": ["plugins", "examples"],
                "enabled_plugins": [],
                "disabled_plugins": [],
            },
            "middleware": {
                "error_handler": {
                    "include_traceback": False,
                },
                "logging": {
                    "log_request": True,
                    "log_response": True,
                },
                "auth": {
                    "enabled": False,
                    "required": True,
                    "exempt_methods": [],
                },
                "cache": {
                    "enabled": False,
                    "default_ttl": 300,
                    "max_size": 1000,
                },
            },
        }

    def _merge_config(self, base: dict[str, Any], override: dict[str, Any]) -> None:
        """递归合并配置字典，override 中的值覆盖 base 中的同名键。"""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value

    def _load_from_yaml(self, config: dict[str, Any]) -> None:
        """从 YAML 文件加载配置。"""
        project_root = _find_project_root()
        config_path = project_root / self._config_file

        if not config_path.exists():
            return

        try:
            with open(config_path, encoding="utf-8") as f:
                yaml_config = yaml.safe_load(f) or {}
            if isinstance(yaml_config, dict):
                self._merge_config(config, yaml_config)
        except Exception as e:
            print(f"Warning: Cannot load config file {config_path}: {e}", file=sys.stderr)

    def _load_from_env(self, config: dict[str, Any]) -> None:
        """从环境变量加载配置，覆盖 YAML 和默认值。

        映射规则：
            APP_ENV       → app_env
            MCP_HOST      → mcp.host
            LOGGING_LEVEL → logging.level
            … 以此类推
        """
        # 顶层 app_env
        if value := os.environ.get("APP_ENV"):
            config["app_env"] = value

        # 各配置段
        for section_name, (prefix, keys) in _ENV_SECTION_MAP.items():
            # 处理嵌套配置（如 middleware.auth）
            parts = section_name.split(".")
            section = config
            for part in parts:
                if part not in section:
                    section[part] = {}
                section = section[part]

            for key in keys:
                env_key = f"{prefix}{key.upper()}"
                value = os.environ.get(env_key)
                if value is None:
                    continue
                # 根据默认值类型进行转换
                default_val = section.get(key)
                if isinstance(default_val, bool):
                    section[key] = _to_bool(value)
                elif isinstance(default_val, int):
                    section[key] = _to_int(value)
                elif isinstance(default_val, float):
                    section[key] = _to_float(value)
                elif isinstance(default_val, list):
                    section[key] = [v.strip() for v in value.split(",")]
                else:
                    section[key] = value

    # ----------------------------------------------------------
    # 解析到 dataclass
    # ----------------------------------------------------------

    def _parse_config(self) -> None:
        """将原始配置字典解析为 dataclass 实例。"""
        self.app_env: str = self._config.get("app_env", ENV_DEVELOPMENT)

        # MCP 配置
        mcp_raw = self._config.get("mcp", {})
        self.mcp = MCPConfig(**mcp_raw)

        # 日志配置
        logging_raw = self._config.get("logging", {})
        self.logging = LoggingConfig(**logging_raw)

        # 功能开关配置
        features_raw = self._config.get("features", {})
        self.features = FeaturesConfig(**features_raw)

        # 插件配置
        plugins_raw = self._config.get("plugins", {})
        self.plugins = PluginConfig(**plugins_raw)

        # 中间件配置（嵌套 dataclass）
        middleware_raw = self._config.get("middleware", {})
        error_handler_raw = middleware_raw.pop("error_handler", {})
        logging_middleware_raw = middleware_raw.pop("logging", {})
        auth_raw = middleware_raw.pop("auth", {})
        cache_raw = middleware_raw.pop("cache", {})

        self.middleware = MiddlewareConfig(
            error_handler=ErrorHandlerConfig(**error_handler_raw),
            logging=LoggingMiddlewareConfig(**logging_middleware_raw),
            auth=AuthConfig(**auth_raw),
            cache=CacheConfig(**cache_raw),
        )

    # ----------------------------------------------------------
    # 环境判断
    # ----------------------------------------------------------

    @property
    def is_development(self) -> bool:
        """是否为开发环境。"""
        return self.app_env == ENV_DEVELOPMENT

    @property
    def is_testing(self) -> bool:
        """是否为测试环境。"""
        return self.app_env == ENV_TESTING

    @property
    def is_production(self) -> bool:
        """是否为生产环境。"""
        return self.app_env == ENV_PRODUCTION

    # ----------------------------------------------------------
    # 配置校验
    # ----------------------------------------------------------

    def validate(self) -> None:
        """验证配置合法性，配置错误直接阻断程序启动。

        Raises:
            ValueError: 配置不合法时抛出
        """
        # 端口范围校验
        if not (1 <= self.mcp.port <= 65535):
            raise ValueError(f"MCP_PORT must be between 1 and 65535, got {self.mcp.port}")

        # 传输类型校验
        valid_transports = [t.value for t in TransportType]
        if self.mcp.transport not in valid_transports:
            raise ValueError(
                f"MCP_TRANSPORT must be one of {valid_transports}, got '{self.mcp.transport}'"
            )

        # 日志级别校验
        valid_levels = [l.value for l in LogLevel]
        if self.logging.level not in valid_levels:
            raise ValueError(
                f"LOGGING_LEVEL must be one of {valid_levels}, got '{self.logging.level}'"
            )

    # ----------------------------------------------------------
    # 热重载
    # ----------------------------------------------------------

    def reload(self) -> None:
        """重新加载全部配置（YAML + 环境变量），并重新校验。"""
        self._config = self._load_config()
        self._parse_config()
        self.validate()

    # ----------------------------------------------------------
    # 序列化
    # ----------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """将配置转换为字典。"""
        return {
            "app_env": self.app_env,
            "mcp": {
                "server_name": self.mcp.server_name,
                "version": self.mcp.version,
                "transport": self.mcp.transport,
                "host": self.mcp.host,
                "port": self.mcp.port,
                "json_response": self.mcp.json_response,
            },
            "logging": {
                "level": self.logging.level,
                "output": self.logging.output,
                "file_path": self.logging.file_path,
                "rotation": self.logging.rotation,
                "retention": self.logging.retention,
                "format": self.logging.format,
            },
            "features": {
                "tools": self.features.tools,
                "resources": self.features.resources,
                "prompts": self.features.prompts,
                "middleware": self.features.middleware,
                "cache": self.features.cache,
            },
            "plugins": {
                "auto_discovery": self.plugins.auto_discovery,
                "discovery_paths": self.plugins.discovery_paths,
                "enabled_plugins": self.plugins.enabled_plugins,
                "disabled_plugins": self.plugins.disabled_plugins,
            },
            "middleware": {
                "error_handler": {
                    "include_traceback": self.middleware.error_handler.include_traceback,
                },
                "logging": {
                    "log_request": self.middleware.logging.log_request,
                    "log_response": self.middleware.logging.log_response,
                },
                "auth": {
                    "enabled": self.middleware.auth.enabled,
                    "required": self.middleware.auth.required,
                    "exempt_methods": self.middleware.auth.exempt_methods,
                },
                "cache": {
                    "enabled": self.middleware.cache.enabled,
                    "default_ttl": self.middleware.cache.default_ttl,
                    "max_size": self.middleware.cache.max_size,
                },
            },
        }

    def save_to_yaml(self, file_path: str | None = None) -> bool:
        """保存配置到 YAML 文件。"""
        try:
            save_path = Path(file_path) if file_path else Path(self._config_file)
            if not save_path.is_absolute():
                save_path = PROJECT_ROOT / save_path

            save_path.parent.mkdir(parents=True, exist_ok=True)

            with open(save_path, "w", encoding="utf-8") as f:
                yaml.dump(self.to_dict(), f, default_flow_style=False, allow_unicode=True)

            return True
        except Exception:
            return False


# ============================================================
# 全局单例
# ============================================================

settings: Final[Settings] = Settings()
settings.validate()


# ============================================================
# 向后兼容导出
# ============================================================

__all__ = [
    "Settings",
    "settings",
    "MCPConfig",
    "LoggingConfig",
    "FeaturesConfig",
    "PluginConfig",
    "AuthConfig",
    "MiddlewareConfig",
    "ErrorHandlerConfig",
    "LoggingMiddlewareConfig",
    "CacheConfig",
    "LogLevel",
    "LogOutput",
    "TransportType",
    "PROJECT_ROOT",
]
