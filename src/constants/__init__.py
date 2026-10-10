#!/usr/bin/env python3
"""常量定义模块。

统一导出全局常量与 MCP 相关枚举，业务代码应从本包导入，
禁止直接引用子模块或在代码中硬编码常量值。

子模块：
    constants.py  — 全局常量（应用信息、环境标识、配置文件）
    enums.py      — MCP 枚举（TransportType、LogLevel、LogOutput）
"""

from .constants import (
    APP_DESCRIPTION,
    APP_ID,
    APP_NAME,
    APP_VERSION,
    DEFAULT_CONFIG_DIR,
    DEFAULT_CONFIG_FILE,
    ENV_DEVELOPMENT,
    ENV_PRODUCTION,
    ENV_TESTING,
)
from .enums import LogLevel, LogOutput, TransportType

__all__ = [
    "APP_ID",
    "APP_NAME",
    "APP_VERSION",
    "APP_DESCRIPTION",
    "ENV_DEVELOPMENT",
    "ENV_TESTING",
    "ENV_PRODUCTION",
    "DEFAULT_CONFIG_DIR",
    "DEFAULT_CONFIG_FILE",
    "TransportType",
    "LogLevel",
    "LogOutput",
]
