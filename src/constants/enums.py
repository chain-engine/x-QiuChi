#!/usr/bin/env python3
"""MCP 框架枚举定义。

集中定义配置与传输层所需的枚举类型，避免业务代码中出现魔法字符串。
成员采用 (mark, desc) 二元组：mark 为存储值，desc 为中文展示文案。
"""

from .base import StrBaseEnum


class TransportType(StrBaseEnum):
    """MCP 传输类型枚举"""

    STDIO = ("stdio", "标准输入输出")
    SSE = ("sse", "服务器发送事件")
    STREAMABLE_HTTP = ("streamable-http", "可流 HTTP 流")


class LogLevel(StrBaseEnum):
    """日志级别枚举"""

    DEBUG = ("DEBUG", "调试信息")
    INFO = ("INFO", "一般信息")
    WARNING = ("WARNING", "警告")
    ERROR = ("ERROR", "错误")
    CRITICAL = ("CRITICAL", "严重错误，程序可能无法继续运行")


class LogOutput(StrBaseEnum):
    """日志输出目标枚举"""

    STDERR = ("stderr", "标准错误")
    FILE = ("file", "文件")
    BOTH = ("both", "同时输出")
