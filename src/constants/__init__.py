#!/usr/bin/env python3
"""常量定义模块。

统一导出全局常量与 MCP 相关枚举，业务代码应从本包导入，
禁止直接引用子模块或在代码中硬编码常量值。

子模块：
    constants.py  — 全局常量（应用信息、配置文件）
    base.py       — 带描述枚举基类族（BaseEnum、StrBaseEnum）
    enums.py      — MCP 枚举（Environment、TransportType、LogLevel、LogOutput、ServerState、PluginType）
"""

from .base import BaseEnum, StrBaseEnum
from .constants import (
    APP_DESCRIPTION,
    APP_ID,
    APP_NAME,
    APP_VERSION,
    DEFAULT_CONFIG_DIR,
    DEFAULT_CONFIG_FILE,
)
from .enums import (
    Environment,
    LogLevel,
    LogOutput,
    PluginType,
    ServerState,
    TransportType,
)

__all__ = [
    "APP_ID",
    "APP_NAME",
    "APP_VERSION",
    "APP_DESCRIPTION",
    "Environment",
    "DEFAULT_CONFIG_DIR",
    "DEFAULT_CONFIG_FILE",
    "BaseEnum",
    "StrBaseEnum",
    "TransportType",
    "LogLevel",
    "LogOutput",
    "ServerState",
    "PluginType",
]
