#!/usr/bin/env python3
"""通用全局常量。

集中定义应用信息、环境标识、响应消息、
用户字段约束等全局常量。禁止在业务代码中硬编码这些值。
"""

# -- 应用信息 -----------------------------------------------------------
APP_ID: str = "x-QiuChi"
APP_NAME: str = "秋池（QiuChi）"
APP_DESCRIPTION: str = "一个生产级 MCP（Model Context Protocol）服务器框架"
APP_VERSION: str = "0.1.0"

# -- 环境标识 -----------------------------------------------------------
ENV_DEVELOPMENT: str = "development"
ENV_TESTING: str = "testing"
ENV_PRODUCTION: str = "production"

# -- 配置文件 -----------------------------------------------------------
DEFAULT_CONFIG_DIR: str = "."
DEFAULT_CONFIG_FILE: str = "config.yaml"

# -- 用户字段约束 -------------------------------------------------------
USERNAME_MIN_LENGTH: int = 3
USERNAME_MAX_LENGTH: int = 50

# -- 响应消息 -----------------------------------------------------------
MSG_SUCCESS: str = "success"
MSG_INTERNAL_ERROR: str = "Internal server error"
MSG_NOT_FOUND: str = "Resource not found"
MSG_VALIDATION_ERROR: str = "Validation error"
MSG_AUTHENTICATION_FAILED: str = "Authentication failed"
MSG_AUTHORIZATION_DENIED: str = "Permission denied"


