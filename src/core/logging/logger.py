"""
QiuChi 日志模块

基于 loguru 的增强日志系统，支持结构化日志和异步输出。
"""

import sys
from pathlib import Path
from typing import Optional, Union, Dict, Any
from loguru import logger as loguru_logger

from ..config.config import settings


class Logger:
    """
    QiuChi 日志器

    封装 loguru 提供更友好的 API。
    """

    def __init__(self, name: str):
        self.name = name
        self._logger = loguru_logger.bind(name=name)

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


def setup_logging(
    level: Optional[str] = None,
    output: Optional[str] = None,
    file_path: Optional[str] = None,
    rotation: Optional[str] = None,
    retention: Optional[str] = None,
    format: Optional[str] = None,
) -> None:
    """
    设置日志配置

    Args:
        level: 日志级别
        output: 输出目标 (stderr, file, both)
        file_path: 日志文件路径
        rotation: 日志轮转周期
        retention: 日志保留时间
        format: 日志格式
    """
    # 使用配置或参数
    config = settings.logging

    log_level = level or config.level.value
    log_output = output or config.output.value
    log_file_path = file_path or config.file_path
    log_rotation = rotation or config.rotation
    log_retention = retention or config.retention
    log_format = format or config.format

    # 移除默认的处理器
    loguru_logger.remove()

    # 配置控制台输出
    if log_output in ["stderr", "both"]:
        loguru_logger.add(
            sys.stderr,
            level=log_level,
            format=log_format,
            colorize=True,
            backtrace=True,
            diagnose=True,
        )

    # 配置文件输出
    if log_output in ["file", "both"]:
        # 确保日志目录存在
        log_file = Path(log_file_path)
        log_file.parent.mkdir(parents=True, exist_ok=True)

        loguru_logger.add(
            str(log_file),
            level=log_level,
            format=log_format,
            rotation=log_rotation,
            retention=log_retention,
            backtrace=True,
            diagnose=True,
            encoding="utf-8",
        )

    loguru_logger.info(f"Logging initialized (level={log_level}, output={log_output})")


def get_logger(name: str) -> Logger:
    """
    获取命名日志器

    Args:
        name: 日志器名称（通常是模块名）

    Returns:
        Logger 实例
    """
    return Logger(name)


# 默认初始化
setup_logging()