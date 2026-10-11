#!/usr/bin/env python3
"""MCP 框架枚举定义。

集中定义配置与传输层所需的枚举类型，避免业务代码中出现魔法字符串。
成员采用 (mark, desc) 二元组：mark 为存储值，desc 为中文展示文案。
"""

from .base import StrBaseEnum


class Environment(StrBaseEnum):
    """运行环境（对齐配置 app_env，可直接与裸字符串比较）。"""

    DEVELOPMENT = "development", "开发环境"
    TESTING = "testing", "测试环境"
    PRODUCTION = "production", "生产环境"


class LogLevel(StrBaseEnum):
    """日志级别枚举"""

    DEBUG = ("DEBUG", "调试信息")
    INFO = ("INFO", "一般信息")
    WARNING = ("WARNING", "警告")
    ERROR = ("ERROR", "错误")
    CRITICAL = ("CRITICAL", "严重错误，程序可能无法继续运行")


class TransportType(StrBaseEnum):
    """MCP 传输类型枚举"""

    STDIO = ("stdio", "标准输入输出")
    SSE = ("sse", "服务器发送事件")
    STREAMABLE_HTTP = ("streamable-http", "可流 HTTP 流")


class LogOutput(StrBaseEnum):
    """日志输出目标枚举"""

    STDERR = ("stderr", "标准错误")
    FILE = ("file", "文件")
    BOTH = ("both", "同时输出")


class ServerState(StrBaseEnum):
    """服务器生命周期状态枚举"""

    UNINITIALIZED = ("uninitialized", "未初始化")
    INITIALIZING = ("initializing", "初始化中")
    READY = ("ready", "就绪")
    STARTING = ("starting", "启动中")
    RUNNING = ("running", "运行中")
    STOPPING = ("stopping", "停止中")
    STOPPED = ("stopped", "已停止")
    ERROR = ("error", "错误")


class PluginType(StrBaseEnum):
    """插件扩展点类型枚举（tool / resource / prompt）"""

    TOOL = ("tool", "工具")
    RESOURCE = ("resource", "资源")
    PROMPT = ("prompt", "提示词")


class PluginStatus(StrBaseEnum):
    """插件状态枚举"""

    UNLOADED = ("unloaded", "未加载")
    LOADED = ("loaded", "已加载")
    ENABLED = ("enabled", "已启用")
    DISABLED = ("disabled", "已禁用")
    ERROR = ("error", "错误")
