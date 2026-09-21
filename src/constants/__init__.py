#!/usr/bin/env python3
"""常量定义模块。

统一导出全局常量与业务枚举，业务代码应从本包导入，
禁止直接引用子模块或在代码中硬编码常量值。

子模块：
    constants.py  — 全局常量（应用信息、环境标识、响应消息等）
    enums.py      — 业务枚举（CommonStatus、UserStatus、AlertChannel、HttpStatus、HttpMediaType）
    base.py       — 可描述枚举基类（BaseEnum）
"""

from src.constants.constants import (
    API_PREFIX,
    APP_DESCRIPTION,
    APP_ID,
    APP_NAME,
    APP_VERSION,
    CONTEXT_REAL_IP,
    CONTEXT_REQUEST_ID,
    DEFAULT_CONFIG_DIR,
    DEFAULT_CONFIG_FILE,
    ENV_DEVELOPMENT,
    ENV_PRODUCTION,
    ENV_TESTING,
    MSG_AUTHENTICATION_FAILED,
    MSG_AUTHORIZATION_DENIED,
    MSG_INTERNAL_ERROR,
    MSG_NOT_FOUND,
    MSG_SUCCESS,
    MSG_VALIDATION_ERROR,
    REQUEST_ID_HEADER,
    USERNAME_MAX_LENGTH,
    USERNAME_MIN_LENGTH,
)
from src.constants.enums import AlertChannel, CommonStatus, HttpMediaType, HttpStatus, UserStatus

__all__ = [
    "APP_ID",
    "APP_NAME",
    "APP_VERSION",
    "APP_DESCRIPTION",
    "API_PREFIX",
    "ENV_DEVELOPMENT",
    "ENV_TESTING",
    "ENV_PRODUCTION",
    "DEFAULT_CONFIG_DIR",
    "DEFAULT_CONFIG_FILE",
    "REQUEST_ID_HEADER",
    "CONTEXT_REQUEST_ID",
    "CONTEXT_REAL_IP",
    "MSG_SUCCESS",
    "MSG_INTERNAL_ERROR",
    "MSG_NOT_FOUND",
    "MSG_VALIDATION_ERROR",
    "MSG_AUTHENTICATION_FAILED",
    "MSG_AUTHORIZATION_DENIED",
    "USERNAME_MIN_LENGTH",
    "USERNAME_MAX_LENGTH",
    "UserStatus",
    "CommonStatus",
    "AlertChannel",
    "HttpMediaType",
    "HttpStatus",
]
