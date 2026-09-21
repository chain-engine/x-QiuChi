#!/usr/bin/env python3
"""
统一日志管理模块

基于 loguru 实现，支持：
    - **JSON 结构化日志**（默认）：扁平 JSON 格式，适合 Loki / ELK / Datadog 收集
    - **彩色控制台格式**（开发环境）：LOGGING_FORMAT=console 切换
    - **自动注入 request_id**：通过 middleware ``logger.contextualize()`` 实现
    - 日志分级：DEBUG / INFO / WARNING / ERROR / CRITICAL
    - 文件始终输出 JSON（便于后续分析），控制台按配置切换
    - 日志轮转和自动清理

Usage:
    from src.core.logger import logger, setup_logging, get_logger

    # 在应用启动时调用一次
    setup_logging()

    # 在任意模块中使用
    logger.info("Application started")

    # 获取命名日志器
    log = get_logger(__name__)
    log.info("Module loaded")
"""

from __future__ import annotations

import json as _json
import os
import sys
from typing import Optional

from loguru import logger as _logger

# 清除 loguru 默认 handler，由 setup_logging 统一管理
_logger.remove()

_configured: bool = False

# ============================================================
# 常量
# ============================================================

_DEFAULT_REQUEST_ID: str = "-"

# ============================================================
# 彩色控制台格式（开发环境人可读）
# ============================================================

_CONSOLE_FORMAT: str = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "<yellow>{extra[request_id]}</yellow> | "
    "<level>{message}</level>"
)


# ============================================================
# JSON 序列化（生产环境结构化日志）
# ============================================================

def _json_serializer(record: dict) -> str:
    """将 loguru 日志记录序列化为扁平 JSON 字符串。

    输出格式示例::

        {
            "timestamp": "2026-09-14T10:30:00.123456+00:00",
            "level": "INFO",
            "logger": "src.main",
            "function": "create_app",
            "line": 42,
            "message": "Application started",
            "request_id": "550e8400-e29b-41d4-a716-446655440000"
        }

    Args:
        record: loguru 内部日志记录字典

    Returns:
        JSON 字符串（不含尾部换行）
    """
    log_entry: dict[str, object] = {
        "timestamp": record["time"].isoformat(),
        "level": record["level"].name,
        "logger": record["name"],
        "function": record["function"],
        "line": record["line"],
        "message": record["message"],
        "request_id": record["extra"].get("request_id", _DEFAULT_REQUEST_ID),
    }
    if record["exception"] is not None:
        log_entry["exception"] = {
            "type": record["exception"].type.__name__,
            "value": str(record["exception"].value),
        }
    return _json.dumps(log_entry, ensure_ascii=False)


def _json_formatter(record: dict) -> str:
    """loguru format 回调：将日志记录格式化为 JSON 行。

    Args:
        record: loguru 内部日志记录字典

    Returns:
        loguru 格式字符串
    """
    record["extra"]["json_output"] = _json_serializer(record) + "\n"
    return "{extra[json_output]}"


# ============================================================
# Logger 封装类
# ============================================================

class Logger:
    """
    日志器

    封装 loguru 提供更友好的 API，支持命名日志器。
    """

    def __init__(self, name: str):
        self.name = name
        self._logger = _logger.bind(name=name)

    def debug(self, message: str, **kwargs) -> None:
        """调试级别日志"""
        self._logger.opt(depth=1).debug(message, **kwargs)

    def info(self, message: str, **kwargs) -> None:
        """信息级别日志"""
        self._logger.opt(depth=1).info(message, **kwargs)

    def warning(self, message: str, **kwargs) -> None:
        """警告级别日志"""
        self._logger.opt(depth=1).warning(message, **kwargs)

    def error(self, message: str, **kwargs) -> None:
        """错误级别日志"""
        self._logger.opt(depth=1).error(message, **kwargs)

    def critical(self, message: str, **kwargs) -> None:
        """严重级别日志"""
        self._logger.opt(depth=1).critical(message, **kwargs)

    def exception(self, message: str, **kwargs) -> None:
        """异常日志（自动包含堆栈跟踪）"""
        self._logger.opt(depth=1).exception(message, **kwargs)

    def log(self, level: str, message: str, **kwargs) -> None:
        """通用日志方法"""
        self._logger.opt(depth=1).log(level, message, **kwargs)

    def bind(self, **kwargs) -> Logger:
        """绑定额外上下文信息，返回新的 Logger 实例"""
        new_logger = Logger(self.name)
        new_logger._logger = self._logger.bind(**kwargs)
        return new_logger


# ============================================================
# 初始化
# ============================================================

def setup_logging(
    level: Optional[str] = None,
    output: Optional[str] = None,
    file_path: Optional[str] = None,
    rotation: Optional[str] = None,
    retention: Optional[str] = None,
    log_format: Optional[str] = None,
) -> None:
    """初始化日志配置，全局只能调用一次。

    控制台输出格式由 ``log_format`` 决定：
        - ``"json"``    → JSON 结构化（生产默认，适合 Loki / ELK）
        - 其他值        → 彩色人可读（开发环境）

    文件输出**始终**为 JSON 格式，便于日志采集和分析。

    参数为 None 时从 Settings 加载默认值。

    Args:
        level: 日志级别，如 DEBUG、INFO、WARNING、ERROR、CRITICAL
        output: 输出目标，stderr、file、both
        file_path: 日志文件路径
        rotation: 日志轮转周期，如 "1 hour"、"1 day"、"100 MB"
        retention: 日志保留时间，如 "7 days"、"30 days"
        log_format: 控制台日志格式，"json" 或其他
    """
    global _configured

    if _configured:
        return

    from core.config import settings

    config = settings.logging

    log_level: str = level or config.level
    log_output: str = output or config.output
    log_file_path: str = file_path or config.file_path
    log_rotation: str = rotation or config.rotation
    log_retention: str = retention or config.retention
    fmt: str = (log_format or config.format).lower()
    use_json_console: bool = fmt == "json"

    # 确保日志目录存在
    log_dir: str = os.path.dirname(log_file_path)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    _logger.remove()

    # ----------------------------------------------------------
    # 控制台输出
    # ----------------------------------------------------------
    if log_output in ("stderr", "both"):
        if use_json_console:
            _logger.add(
                sink=sys.stderr,
                format=_json_formatter,
                level=log_level,
                enqueue=True,
            )
        else:
            _logger.add(
                sink=sys.stderr,
                format=_CONSOLE_FORMAT,
                level=log_level,
                colorize=True,
                enqueue=True,
            )

    # ----------------------------------------------------------
    # 文件输出（始终 JSON，便于后续分析）
    # ----------------------------------------------------------
    if log_output in ("file", "both"):
        _logger.add(
            sink=log_file_path,
            format=_json_formatter,
            level=log_level,
            rotation=log_rotation,
            retention=log_retention,
            compression="zip",
            enqueue=True,
            encoding="utf-8",
        )

    # ----------------------------------------------------------
    # 兜底：确保所有日志记录都有 request_id 字段
    # ----------------------------------------------------------
    _logger.configure(
        patcher=lambda record: record["extra"].setdefault(
            "request_id", _DEFAULT_REQUEST_ID
        )
    )

    _configured = True
    _logger.info(f"Logging initialized (level={log_level}, output={log_output})")


# ============================================================
# 公开 API
# ============================================================

def get_logger(name: str) -> Logger:
    """获取命名日志器。

    Args:
        name: 日志器名称（通常是模块名）

    Returns:
        Logger 实例
    """
    return Logger(name)


def get_log_file_path() -> str:
    """获取日志文件路径。

    Returns:
        str: 日志文件路径
    """
    from core.config import settings

    return settings.logging.file_path


# 全局日志实例
logger = _logger

__all__ = ["logger", "Logger", "setup_logging", "get_logger", "get_log_file_path"]
