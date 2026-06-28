"""
QiuChi 核心类型定义

定义共享的枚举和类型，避免循环导入。
"""

from enum import Enum


class TransportType(str, Enum):
    """MCP 传输类型枚举"""
    STDIO = "stdio"
    SSE = "sse"
    STREAMABLE_HTTP = "streamable-http"


class LogLevel(str, Enum):
    """日志级别枚举"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogOutput(str, Enum):
    """日志输出目标枚举"""
    STDERR = "stderr"
    FILE = "file"
    BOTH = "both"


__all__ = ["TransportType", "LogLevel", "LogOutput"]