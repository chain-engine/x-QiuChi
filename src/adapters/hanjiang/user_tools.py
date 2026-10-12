"""
汉江用户管理域 MCP 工具

将汉江管理系统用户管理 API（创建 / 列表 / 详情 / 更新 / 启停 / 重置密码 / 删除）
转接为 MCP 工具。所有操作以服务凭据账号身份执行，其权限决定 AI 操作边界。

说明：
- status 枚举：active（启用）/ inactive（禁用）/ locked（锁定）
- gender 枚举：male / female
- 写操作（create/update/status/reset/delete）不自动重试，避免重复副作用
"""

from __future__ import annotations

import json
from typing import Any

from src.adapters.hanjiang.client import HanJiangError, get_client
from src.plugins import tool_decorator


def _format_result(data: Any) -> str:
    """将汉江响应 data 格式化为美化 JSON 文本。"""
    return json.dumps(data, ensure_ascii=False, indent=2)


def _build_update_payload(**fields: Any) -> dict[str, Any]:
    """组装更新请求体：仅保留调用方显式提供的字段（与汉江 UserUpdateRequest 全可选语义一致）。"""
    return {key: value for key, value in fields.items() if value is not None}


@tool_decorator(category="hanjiang.user", subcategory="manage", tags=["hanjiang", "user", "create"])
async def hanjiang_user_create(
    username: str,
    email: str,
    password: str,
    name: str,
    role_ids: list[int],
    phone: str | None = None,
    gender: str | None = None,
    birthday: str | None = None,
    avatar_url: str | None = None,
    status: str = "active",
) -> str:
    """
    创建汉江用户（邮箱/用户名全局唯一；password 参数自动脱敏不入日志）

    Args:
        username: 用户名（3-50 位）
        email: 邮箱（全局唯一，格式校验）
        password: 初始密码（8-64 位，服务端 bcrypt 哈希存储）
        name: 姓名
        role_ids: 角色ID列表（至少 1 个）
        phone: 手机号（可选）
        gender: 性别 male/female（可选）
        birthday: 生日 YYYY-MM-DD（可选）
        avatar_url: 头像URL（可选）
        status: 状态 active/inactive/locked（默认 active）

    Returns:
        创建的用户信息
    """
    payload: dict[str, Any] = {
        "username": username,
        "email": email,
        "password": password,
        "name": name,
        "role_ids": role_ids,
        "status": status,
    }
    if phone is not None:
        payload["phone"] = phone
    if gender is not None:
        payload["gender"] = gender
    if birthday is not None:
        payload["birthday"] = birthday
    if avatar_url is not None:
        payload["avatar_url"] = avatar_url
    try:
        data = await get_client().create_user(payload)
        return _format_result(data)
    except HanJiangError as e:
        return f"创建用户失败: {e.message}"


@tool_decorator(category="hanjiang.user", subcategory="query", tags=["hanjiang", "user", "list"])
async def hanjiang_user_list(
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
    status: str | None = None,
) -> str:
    """
    分页查询汉江用户列表（支持关键字/状态过滤）

    Args:
        page: 页码（从 1 开始）
        page_size: 每页条数（默认 20）
        keyword: 关键字过滤（用户名/邮箱/姓名模糊匹配，可选）
        status: 状态过滤 active/inactive/locked（可选）

    Returns:
        分页结果：items / total / page / page_size / total_pages
    """
    params: dict[str, Any] = {"page": page, "page_size": page_size}
    if keyword is not None:
        params["keyword"] = keyword
    if status is not None:
        params["status"] = status
    try:
        data = await get_client().list_users(params)
        return _format_result(data)
    except HanJiangError as e:
        return f"查询用户列表失败: {e.message}"


@tool_decorator(category="hanjiang.user", subcategory="query", tags=["hanjiang", "user", "detail"])
async def hanjiang_user_get(user_id: int) -> str:
    """
    查询汉江用户详情

    Args:
        user_id: 用户ID

    Returns:
        用户详细信息
    """
    try:
        data = await get_client().get_user(user_id)
        return _format_result(data)
    except HanJiangError as e:
        return f"查询用户失败: {e.message}（用户可能不存在）"


@tool_decorator(category="hanjiang.user", subcategory="manage", tags=["hanjiang", "user", "update"])
async def hanjiang_user_update(
    user_id: int,
    username: str | None = None,
    email: str | None = None,
    password: str | None = None,
    name: str | None = None,
    phone: str | None = None,
    avatar_url: str | None = None,
    birthday: str | None = None,
    gender: str | None = None,
    role_ids: list[int] | None = None,
    status: str | None = None,
) -> str:
    """
    更新汉江用户信息（仅更新提供的字段；password 提供时重新哈希；password 参数自动脱敏）

    Args:
        user_id: 用户ID
        username: 用户名（3-50 位，可选）
        email: 邮箱（全局唯一，可选）
        password: 新密码（8-64 位，可选）
        name: 姓名（可选）
        phone: 手机号（可选）
        avatar_url: 头像URL（可选）
        birthday: 生日 YYYY-MM-DD（可选）
        gender: 性别 male/female（可选）
        role_ids: 角色ID列表（可选）
        status: 状态 active/inactive/locked（可选）

    Returns:
        更新后的用户信息
    """
    payload = _build_update_payload(
        username=username,
        email=email,
        password=password,
        name=name,
        phone=phone,
        avatar_url=avatar_url,
        birthday=birthday,
        gender=gender,
        role_ids=role_ids,
        status=status,
    )
    try:
        data = await get_client().update_user(user_id, payload)
        return _format_result(data)
    except HanJiangError as e:
        return f"更新用户失败: {e.message}"


@tool_decorator(category="hanjiang.user", subcategory="manage", tags=["hanjiang", "user", "status"])
async def hanjiang_user_status(user_id: int, status: str) -> str:
    """
    启用/禁用汉江用户账号

    Args:
        user_id: 用户ID
        status: 目标状态 active/inactive/locked

    Returns:
        操作结果
    """
    try:
        data = await get_client().update_user_status(user_id, status)
        return _format_result(data)
    except HanJiangError as e:
        return f"更新用户状态失败: {e.message}"


@tool_decorator(
    category="hanjiang.user", subcategory="manage", tags=["hanjiang", "user", "reset-password"]
)
async def hanjiang_user_reset_password(user_id: int, new_password: str) -> str:
    """
    管理员重置汉江用户密码（new_password 参数自动脱敏不入日志）

    Args:
        user_id: 用户ID
        new_password: 新密码（8-64 位）

    Returns:
        操作结果
    """
    try:
        data = await get_client().reset_user_password(user_id, new_password)
        return _format_result(data)
    except HanJiangError as e:
        return f"重置密码失败: {e.message}"


@tool_decorator(category="hanjiang.user", subcategory="manage", tags=["hanjiang", "user", "delete"])
async def hanjiang_user_delete(user_id: int) -> str:
    """
    删除汉江用户（软删除，仅禁用账号）

    Args:
        user_id: 用户ID

    Returns:
        操作结果
    """
    try:
        data = await get_client().delete_user(user_id)
        return _format_result(data)
    except HanJiangError as e:
        return f"删除用户失败: {e.message}"


__all__ = [
    "hanjiang_user_create",
    "hanjiang_user_list",
    "hanjiang_user_get",
    "hanjiang_user_update",
    "hanjiang_user_status",
    "hanjiang_user_reset_password",
    "hanjiang_user_delete",
]
