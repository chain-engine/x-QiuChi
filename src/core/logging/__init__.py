"""
QiuChi 日志系统

基于 loguru 的日志系统，支持：
- 多输出目标（控制台、文件）
- 结构化日志
- 日志轮转和保留
- 异步日志
"""

from .logger import get_logger, setup_logging, Logger

__all__ = ["get_logger", "setup_logging", "Logger"]