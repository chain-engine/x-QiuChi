#!/usr/bin/env python3
"""
通用工具函数模块

本模块提供项目中常用的通用工具函数，包括：
    - UUID 生成
    - 客户端 IP 提取
    - 敏感数据脱敏
    - 时间戳格式化
"""

import uuid
from datetime import UTC
from typing import Any

from fastapi import Request


def generate_request_id() -> str:
    """生成唯一请求 ID。

    使用 UUID4 算法生成全局唯一的请求标识符。

    Returns:
        str: UUID4 格式的请求 ID
    """
    return str(uuid.uuid4())


def get_client_ip(request: Request) -> str:
    """从请求中提取客户端真实 IP 地址。

    按优先级依次检查代理头和直接连接地址：
        1. X-Forwarded-For（第一个地址）
        2. X-Real-IP
        3. request.client.host

    Args:
        request: FastAPI 请求对象

    Returns:
        str: 客户端 IP 地址
    """
    forwarded: str | None = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()

    real_ip: str | None = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    if request.client:
        return request.client.host

    return "unknown"


def mask_sensitive(data: dict[str, Any], keys: list[str] | None = None) -> dict[str, Any]:
    """对字典中的敏感字段进行脱敏处理。

    将指定键的值替换为 "****"，用于安全日志输出。
    默认脱敏字段：password、secret、token、key、authorization。

    Args:
        data: 原始数据字典
        keys: 需要脱敏的键名列表（不区分大小写）

    Returns:
        dict[str, Any]: 脱敏后的数据副本（不修改原始数据）
    """
    default_keys: list[str] = ["password", "secret", "token", "key", "authorization"]
    sensitive_keys: set[str] = {k.lower() for k in (keys or default_keys)}

    masked: dict[str, Any] = {}
    for k, v in data.items():
        if k.lower() in sensitive_keys:
            masked[k] = "****"
        elif isinstance(v, dict):
            masked[k] = mask_sensitive(v, keys)
        else:
            masked[k] = v

    return masked


def datetime_now_iso() -> str:
    """获取当前 UTC 时间的 ISO 8601 格式字符串。

    Returns:
        str: ISO 8601 格式的 UTC 时间戳
    """
    from datetime import datetime

    return datetime.now(UTC).isoformat()
