#!/usr/bin/env python3
"""通用全局常量。

集中定义应用信息、环境标识、请求上下文键、响应消息、
用户字段约束等全局常量。禁止在业务代码中硬编码这些值。
"""

# -- 应用信息 -----------------------------------------------------------
APP_ID: str = "x-HanJiang"
APP_NAME: str = "汉江（HanJiang）"
APP_DESCRIPTION: str = "一个基于 FastAPI 框架深度封装的生产级 Python Web 应用框架"
APP_VERSION: str = "0.1.0"

# -- API ----------------------------------------------------------------
API_PREFIX: str = "/api/v1"

# -- 环境标识 -----------------------------------------------------------
ENV_DEVELOPMENT: str = "development"
ENV_TESTING: str = "testing"
ENV_PRODUCTION: str = "production"

# -- 配置文件 -----------------------------------------------------------
DEFAULT_CONFIG_DIR: str = "."
DEFAULT_CONFIG_FILE: str = "config.yaml"

# -- 请求上下文 ---------------------------------------------------------
REQUEST_ID_HEADER: str = "X-Request-ID"        # 请求头中的 Request ID 字段名
CONTEXT_REQUEST_ID: str = "request_id"          # request.state 中的键
CONTEXT_REAL_IP: str = "real_ip"                # request.state 中的键

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


