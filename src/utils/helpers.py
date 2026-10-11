#!/usr/bin/env python3
"""
通用工具函数

集中放置跨模块复用的公共辅助函数（原位于 src/core/config.py，
按单一职责抽离至此）：

    - PROJECT_ROOT / find_project_root — 项目根目录定位
    - to_bool / to_int / to_float — 宽松类型转换（配置解析用）
    - get_package_version — 包版本读取（唯一事实源 pyproject.toml）
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

# ============================================================
# 项目根目录
# ============================================================

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]


def find_project_root() -> Path:
    """返回项目根目录。"""
    return PROJECT_ROOT


# ============================================================
# 宽松类型转换
# ============================================================


def to_bool(value: Any) -> bool:
    """将值转换为布尔类型。"""
    if isinstance(value, bool):
        return value
    return str(value).lower() in ("true", "1", "yes", "on")


def to_int(value: Any, default: int = 0) -> int:
    """将值转换为整数类型。"""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def to_float(value: Any, default: float = 0.0) -> float:
    """将值转换为浮点类型。"""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


# ============================================================
# 版本号（唯一事实源：pyproject.toml）
# ============================================================


def get_package_version() -> str:
    """从 pyproject.toml 读取版本号（唯一事实源）。

    项目由 uv 管理，自身会被安装为可编辑包，因此
    ``importlib.metadata.version("x-QiuChi")`` 返回 pyproject.toml 的 version；
    未安装时回退到与 pyproject 一致的 0.1.0。
    """
    try:
        from importlib.metadata import version

        return version("x-QiuChi")
    except Exception:
        return "0.1.0"
