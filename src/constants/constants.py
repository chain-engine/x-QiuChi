#!/usr/bin/env python3
"""通用全局常量。

集中定义应用信息、环境标识、配置文件等全局常量。禁止在业务代码中硬编码这些值。
"""

# -- 应用信息 -----------------------------------------------------------
APP_ID: str = "x-QiuChi"
APP_NAME: str = "秋池（QiuChi）"
APP_DESCRIPTION: str = "一个生产级 MCP（Model Context Protocol）服务器框架"
APP_VERSION: str = "0.1.0"


# -- 配置文件 -----------------------------------------------------------
DEFAULT_CONFIG_DIR: str = "."
DEFAULT_CONFIG_FILE: str = "config.yaml"
