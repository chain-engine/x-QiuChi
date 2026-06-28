"""
QiuChi 配置管理模块

基于 Pydantic Settings 的配置系统，支持：
- 环境变量加载（自动前缀转换）
- YAML 配置文件
- 配置验证和类型转换
- 热重载支持
- 多环境配置

使用示例：
    >>> from src.core.config import settings
    >>> print(settings.server_name)
    >>> print(settings.transport)
    >>> settings.reload()  # 重新加载配置
"""

from .config import Settings, settings

__all__ = ["Settings", "settings"]